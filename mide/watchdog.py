"""Process-wide reliability guard for scheduled scans."""

from __future__ import annotations

from dataclasses import dataclass
import logging
import threading
import time
from typing import Callable, TypeVar


T = TypeVar("T")


class ScanAlreadyRunning(RuntimeError):
    """Raised when another Streamlit session already owns the scanner."""


@dataclass(frozen=True)
class ScanFailure:
    attempt: int
    error_type: str
    message: str


class ScanWatchdog:
    """Serialize scans and retry transient failures with bounded backoff.

    The lock belongs to the Python process rather than a Streamlit session, so
    two browser sessions (or overlapping reruns) cannot scan concurrently.
    """

    def __init__(
        self,
        *,
        max_attempts: int = 3,
        backoff_seconds: tuple[float, ...] = (1.0, 3.0),
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if max_attempts < 1:
            raise ValueError("max_attempts must be at least one")
        self.max_attempts = max_attempts
        self.backoff_seconds = backoff_seconds
        self._sleep = sleep
        self._lock = threading.Lock()
        self.last_failures: list[ScanFailure] = []

    def run(
        self,
        scan: Callable[[], T],
        *,
        before_retry: Callable[[], None] | None = None,
        on_acquired: Callable[[], None] | None = None,
        on_finished: Callable[[], None] | None = None,
    ) -> T:
        if not self._lock.acquire(blocking=False):
            raise ScanAlreadyRunning("a scan is already running in this process")
        try:
            if on_acquired is not None:
                on_acquired()
            self.last_failures = []
            for attempt in range(1, self.max_attempts + 1):
                try:
                    return scan()
                except Exception as exc:
                    failure = ScanFailure(attempt, type(exc).__name__, str(exc))
                    self.last_failures.append(failure)
                    logging.getLogger(__name__).exception(
                        "Scan attempt %s/%s failed", attempt, self.max_attempts
                    )
                    if attempt == self.max_attempts:
                        raise
                    if before_retry is not None:
                        before_retry()
                    delay_index = min(attempt - 1, len(self.backoff_seconds) - 1)
                    delay = self.backoff_seconds[delay_index] if self.backoff_seconds else 0
                    if delay > 0:
                        self._sleep(delay)
            raise AssertionError("unreachable")
        finally:
            try:
                if on_finished is not None:
                    on_finished()
            finally:
                self._lock.release()

    @property
    def is_running(self) -> bool:
        """Return whether this process currently has an active scan owner."""
        return self._lock.locked()


# Kept in this small, stable module so Streamlit session reruns share one lock.
PROCESS_SCAN_WATCHDOG = ScanWatchdog()

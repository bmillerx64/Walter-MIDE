"""Process-wide reliability guard for scheduled scans."""

from __future__ import annotations

from dataclasses import dataclass
import logging
import threading
import time
from typing import Callable, TypeVar


T = TypeVar("T")

# GS412: once one session has successfully finished provider work, allow a short
# process-wide handoff window for that completed result to be published/adopted by
# other Streamlit sessions. Without this guard a waiting session can acquire the
# watchdog in the tiny release->publication gap and launch a duplicate scan only
# a few seconds after the previous one.
COMPLETED_SCAN_HANDOFF_GUARD_SECONDS = 10.0


class ScanAlreadyRunning(RuntimeError):
    """Raised when another Streamlit session already owns/recently owned the scanner."""


@dataclass(frozen=True)
class ScanFailure:
    attempt: int
    error_type: str
    message: str


class ScanWatchdog:
    """Serialize scans and retry transient failures with bounded backoff.

    The lock belongs to the Python process rather than a Streamlit session, so
    two browser sessions (or overlapping reruns) cannot scan concurrently.

    GS412 also protects the brief successful-completion handoff boundary. The
    normal 60-second scheduler remains authoritative; this is only a small
    duplicate-start safety belt while another session adopts the just-completed
    process result.
    """

    def __init__(
        self,
        *,
        max_attempts: int = 3,
        backoff_seconds: tuple[float, ...] = (1.0, 3.0),
        sleep: Callable[[float], None] = time.sleep,
        monotonic: Callable[[], float] = time.monotonic,
        completed_handoff_guard_seconds: float = COMPLETED_SCAN_HANDOFF_GUARD_SECONDS,
    ) -> None:
        if max_attempts < 1:
            raise ValueError("max_attempts must be at least one")
        self.max_attempts = max_attempts
        self.backoff_seconds = backoff_seconds
        self._sleep = sleep
        self._monotonic = monotonic
        self.completed_handoff_guard_seconds = max(
            0.0, float(completed_handoff_guard_seconds)
        )
        self._lock = threading.Lock()
        self._last_successful_finish_monotonic: float | None = None
        self.last_failures: list[ScanFailure] = []

    def _handoff_guard_active(self) -> bool:
        previous = self._last_successful_finish_monotonic
        if previous is None or self.completed_handoff_guard_seconds <= 0:
            return False
        elapsed = self._monotonic() - previous
        return 0.0 <= elapsed < self.completed_handoff_guard_seconds

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
        succeeded = False
        try:
            if self._handoff_guard_active():
                raise ScanAlreadyRunning(
                    "a completed scan is still in the cross-session handoff window"
                )
            if on_acquired is not None:
                on_acquired()
            self.last_failures = []
            for attempt in range(1, self.max_attempts + 1):
                try:
                    result = scan()
                    succeeded = True
                    return result
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
                if on_finished is not None and not self._handoff_guard_active():
                    # A guard rejection did not acquire scan lifecycle ownership.
                    # For an actual scan attempt, preserve the historical callback.
                    on_finished()
            finally:
                if succeeded:
                    self._last_successful_finish_monotonic = self._monotonic()
                self._lock.release()

    @property
    def is_running(self) -> bool:
        """Return whether this process currently has an active scan owner."""
        return self._lock.locked()


# Kept in this small, stable module so Streamlit session reruns share one lock.
PROCESS_SCAN_WATCHDOG = ScanWatchdog()

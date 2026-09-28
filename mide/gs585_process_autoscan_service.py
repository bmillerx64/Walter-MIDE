"""GS585: process-owned AutoScan cadence independent of Streamlit reruns.

Monday live evidence showed the scanner itself remains fast while scan start
intervals drift when the Streamlit/browser timer stalls. This module supplies one
small daemon scheduler per Python process. It owns cadence only; the existing
process watchdog remains the sole scan-concurrency authority and the worker
continues to use Walter's unchanged market/trading pipeline.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import threading
import time
from typing import Callable


Worker = Callable[[], bool]


@dataclass(frozen=True)
class ProcessAutoScanSnapshot:
    enabled: bool
    running: bool
    refresh_seconds: int
    last_started_at: datetime | None
    last_finished_at: datetime | None
    next_due_monotonic: float | None
    last_error: str | None
    generation: int


_LOCK = threading.RLock()
_WAKE = threading.Event()
_THREAD: threading.Thread | None = None
_ENABLED = False
_RUNNING = False
_REFRESH_SECONDS = 60
_WORKER: Worker | None = None
_LAST_STARTED_AT: datetime | None = None
_LAST_FINISHED_AT: datetime | None = None
_NEXT_DUE_MONOTONIC: float | None = None
_LAST_ERROR: str | None = None
_GENERATION = 0
_PROCESS_STATE: dict[str, object] = {}


def process_state() -> dict[str, object]:
    """Return process-owned scanner state, never Streamlit session state."""
    return _PROCESS_STATE


def snapshot() -> ProcessAutoScanSnapshot:
    with _LOCK:
        return ProcessAutoScanSnapshot(
            enabled=_ENABLED,
            running=_RUNNING,
            refresh_seconds=_REFRESH_SECONDS,
            last_started_at=_LAST_STARTED_AT,
            last_finished_at=_LAST_FINISHED_AT,
            next_due_monotonic=_NEXT_DUE_MONOTONIC,
            last_error=_LAST_ERROR,
            generation=_GENERATION,
        )


def _ensure_thread_locked() -> None:
    global _THREAD
    if _THREAD is not None and _THREAD.is_alive():
        return
    _THREAD = threading.Thread(
        target=_scheduler_loop,
        name="walter-process-autoscan",
        daemon=True,
    )
    _THREAD.start()


def configure(
    *,
    enabled: bool,
    refresh_seconds: int,
    worker: Worker | None,
    initial_completed_at: datetime | None = None,
) -> ProcessAutoScanSnapshot:
    """Configure process cadence without resetting it on every Streamlit rerun."""
    global _ENABLED, _REFRESH_SECONDS, _WORKER, _NEXT_DUE_MONOTONIC, _GENERATION
    with _LOCK:
        was_enabled = _ENABLED
        previous_refresh = _REFRESH_SECONDS
        _ENABLED = bool(enabled)
        _REFRESH_SECONDS = max(1, int(refresh_seconds))
        if worker is not None:
            _WORKER = worker
        _GENERATION += 1
        if _ENABLED:
            _ensure_thread_locked()
            if not was_enabled or _NEXT_DUE_MONOTONIC is None:
                if initial_completed_at is None:
                    _NEXT_DUE_MONOTONIC = time.monotonic()
                else:
                    age = max(
                        0.0,
                        (
                            datetime.now().astimezone()
                            - initial_completed_at.astimezone()
                        ).total_seconds(),
                    )
                    _NEXT_DUE_MONOTONIC = time.monotonic() + max(
                        0.0, float(_REFRESH_SECONDS) - age
                    )
            elif previous_refresh != _REFRESH_SECONDS and _LAST_STARTED_AT is not None:
                age = max(
                    0.0,
                    (
                        datetime.now().astimezone()
                        - _LAST_STARTED_AT.astimezone()
                    ).total_seconds(),
                )
                _NEXT_DUE_MONOTONIC = time.monotonic() + max(
                    0.0, float(_REFRESH_SECONDS) - age
                )
        else:
            _NEXT_DUE_MONOTONIC = None
        current = snapshot()
    _WAKE.set()
    return current


def note_scan_started(started_at: datetime | None = None) -> None:
    """Anchor start-to-start cadence at the real watchdog acquisition boundary."""
    global _LAST_STARTED_AT, _NEXT_DUE_MONOTONIC, _LAST_ERROR
    now_mono = time.monotonic()
    with _LOCK:
        _LAST_STARTED_AT = started_at or datetime.now().astimezone()
        _NEXT_DUE_MONOTONIC = now_mono + float(_REFRESH_SECONDS)
        _LAST_ERROR = None
    _WAKE.set()


def note_scan_finished(finished_at: datetime | None = None) -> None:
    global _LAST_FINISHED_AT
    with _LOCK:
        _LAST_FINISHED_AT = finished_at or datetime.now().astimezone()


def _schedule_retry(delay_seconds: float, error: object | None = None) -> None:
    global _NEXT_DUE_MONOTONIC, _LAST_ERROR
    with _LOCK:
        _NEXT_DUE_MONOTONIC = time.monotonic() + max(1.0, float(delay_seconds))
        _LAST_ERROR = None if error is None else str(error)


def _scheduler_loop() -> None:
    global _RUNNING, _LAST_ERROR, _NEXT_DUE_MONOTONIC
    while True:
        with _LOCK:
            enabled = _ENABLED
            worker = _WORKER
            due = _NEXT_DUE_MONOTONIC
        if not enabled or worker is None or due is None:
            _WAKE.wait(1.0)
            _WAKE.clear()
            continue

        wait = due - time.monotonic()
        if wait > 0:
            _WAKE.wait(min(wait, 1.0))
            _WAKE.clear()
            continue

        with _LOCK:
            if not _ENABLED or _RUNNING:
                continue
            # Claim this deadline before worker execution. note_scan_started()
            # replaces it with the exact watchdog-acquisition cadence boundary.
            _RUNNING = True
            _NEXT_DUE_MONOTONIC = None

        ok = False
        error: object | None = None
        try:
            ok = bool(worker())
        except Exception as exc:  # worker owns detailed logging
            error = exc
        finally:
            with _LOCK:
                _RUNNING = False
                if _ENABLED and _NEXT_DUE_MONOTONIC is None:
                    # Watchdog collision/transient failure: retry soon. A normal
                    # successful worker calls note_scan_started() and already has
                    # the next 60-second deadline anchored to actual scan start.
                    _schedule_retry(5.0 if not ok else _REFRESH_SECONDS, error)
            _WAKE.set()


def _reset_for_tests() -> None:
    global _THREAD, _ENABLED, _RUNNING, _REFRESH_SECONDS, _WORKER
    global _LAST_STARTED_AT, _LAST_FINISHED_AT, _NEXT_DUE_MONOTONIC
    global _LAST_ERROR, _GENERATION
    with _LOCK:
        _ENABLED = False
        _RUNNING = False
        _REFRESH_SECONDS = 60
        _WORKER = None
        _LAST_STARTED_AT = None
        _LAST_FINISHED_AT = None
        _NEXT_DUE_MONOTONIC = None
        _LAST_ERROR = None
        _GENERATION = 0
        _PROCESS_STATE.clear()
        _THREAD = None
    _WAKE.set()

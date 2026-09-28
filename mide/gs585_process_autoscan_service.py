"""GS585/GS588: process-owned AutoScan cadence independent of Streamlit reruns.

GS585 moved automatic cadence out of Streamlit/browser timing. Monday live
validation later exposed a warm-deploy seam: multiple generations of this module
could each retain a daemon scheduler thread even though the process watchdog still
prevented overlap. GS588 stores all scheduler runtime on the already process-wide
watchdog singleton so warm app generations reuse one thread, one deadline, and one
worker.

This module owns cadence only. The watchdog remains the sole scan-concurrency
authority and the worker continues to use Walter's unchanged market/trading
pipeline.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import threading
import time
from typing import Callable, Any


Worker = Callable[[], bool]
_RUNTIME_ATTR = "_walter_gs585_process_autoscan_runtime"
_RUNTIME_SCHEMA = 2


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
    thread_ident: int | None


def _new_runtime() -> dict[str, Any]:
    return {
        "schema": _RUNTIME_SCHEMA,
        "lock": threading.RLock(),
        "wake": threading.Event(),
        "thread": None,
        "enabled": False,
        "running": False,
        "refresh_seconds": 60,
        "worker": None,
        "last_started_at": None,
        "last_finished_at": None,
        "next_due_monotonic": None,
        "last_error": None,
        "generation": 0,
        "process_state": {},
    }


def _runtime() -> dict[str, Any]:
    """Return one scheduler runtime anchored to the process-wide watchdog.

    The watchdog singleton already survives Streamlit warm reruns and is the
    authority that serialized the duplicate GS585 generations observed live.
    Attaching scheduler state to that same object prevents a re-imported module
    from manufacturing another cadence thread.
    """
    from .watchdog import PROCESS_SCAN_WATCHDOG

    runtime = getattr(PROCESS_SCAN_WATCHDOG, _RUNTIME_ATTR, None)
    if not isinstance(runtime, dict) or runtime.get("schema") != _RUNTIME_SCHEMA:
        runtime = _new_runtime()
        setattr(PROCESS_SCAN_WATCHDOG, _RUNTIME_ATTR, runtime)
    return runtime


def process_state() -> dict[str, object]:
    """Return process-owned scanner state, never Streamlit session state."""
    return _runtime()["process_state"]


def snapshot() -> ProcessAutoScanSnapshot:
    runtime = _runtime()
    with runtime["lock"]:
        thread = runtime.get("thread")
        return ProcessAutoScanSnapshot(
            enabled=bool(runtime["enabled"]),
            running=bool(runtime["running"]),
            refresh_seconds=int(runtime["refresh_seconds"]),
            last_started_at=runtime["last_started_at"],
            last_finished_at=runtime["last_finished_at"],
            next_due_monotonic=runtime["next_due_monotonic"],
            last_error=runtime["last_error"],
            generation=int(runtime["generation"]),
            thread_ident=(
                int(thread.ident)
                if thread is not None and thread.ident is not None
                else None
            ),
        )


def _ensure_thread_locked(runtime: dict[str, Any]) -> None:
    thread = runtime.get("thread")
    if thread is not None and thread.is_alive():
        return
    thread = threading.Thread(
        target=_scheduler_loop,
        args=(runtime,),
        name="walter-process-autoscan",
        daemon=True,
    )
    runtime["thread"] = thread
    thread.start()


def configure(
    *,
    enabled: bool,
    refresh_seconds: int,
    worker: Worker | None,
    initial_completed_at: datetime | None = None,
) -> ProcessAutoScanSnapshot:
    """Configure process cadence without resetting it on every Streamlit rerun."""
    runtime = _runtime()
    with runtime["lock"]:
        was_enabled = bool(runtime["enabled"])
        previous_refresh = int(runtime["refresh_seconds"])
        runtime["enabled"] = bool(enabled)
        runtime["refresh_seconds"] = max(1, int(refresh_seconds))
        if worker is not None:
            # Warm reruns replace only the callable; the one process scheduler
            # thread and its deadline remain intact.
            runtime["worker"] = worker
        runtime["generation"] = int(runtime["generation"]) + 1
        if runtime["enabled"]:
            _ensure_thread_locked(runtime)
            if not was_enabled or runtime["next_due_monotonic"] is None:
                if initial_completed_at is None:
                    runtime["next_due_monotonic"] = time.monotonic()
                else:
                    age = max(
                        0.0,
                        (
                            datetime.now().astimezone()
                            - initial_completed_at.astimezone()
                        ).total_seconds(),
                    )
                    runtime["next_due_monotonic"] = time.monotonic() + max(
                        0.0, float(runtime["refresh_seconds"]) - age
                    )
            elif (
                previous_refresh != runtime["refresh_seconds"]
                and runtime["last_started_at"] is not None
            ):
                age = max(
                    0.0,
                    (
                        datetime.now().astimezone()
                        - runtime["last_started_at"].astimezone()
                    ).total_seconds(),
                )
                runtime["next_due_monotonic"] = time.monotonic() + max(
                    0.0, float(runtime["refresh_seconds"]) - age
                )
        else:
            runtime["next_due_monotonic"] = None
        current = snapshot()
    runtime["wake"].set()
    return current


def note_scan_started(started_at: datetime | None = None) -> None:
    """Anchor start-to-start cadence at the real watchdog acquisition boundary."""
    runtime = _runtime()
    now_mono = time.monotonic()
    with runtime["lock"]:
        runtime["last_started_at"] = started_at or datetime.now().astimezone()
        runtime["next_due_monotonic"] = (
            now_mono + float(runtime["refresh_seconds"])
        )
        runtime["last_error"] = None
    runtime["wake"].set()


def note_scan_finished(finished_at: datetime | None = None) -> None:
    runtime = _runtime()
    with runtime["lock"]:
        runtime["last_finished_at"] = (
            finished_at or datetime.now().astimezone()
        )


def _schedule_retry(
    runtime: dict[str, Any],
    delay_seconds: float,
    error: object | None = None,
) -> None:
    with runtime["lock"]:
        runtime["next_due_monotonic"] = (
            time.monotonic() + max(1.0, float(delay_seconds))
        )
        runtime["last_error"] = None if error is None else str(error)


def _scheduler_loop(runtime: dict[str, Any]) -> None:
    """Run the single process cadence loop against the shared runtime object."""
    while True:
        with runtime["lock"]:
            enabled = bool(runtime["enabled"])
            worker = runtime["worker"]
            due = runtime["next_due_monotonic"]
        if not enabled or worker is None or due is None:
            runtime["wake"].wait(1.0)
            runtime["wake"].clear()
            continue

        wait = float(due) - time.monotonic()
        if wait > 0:
            runtime["wake"].wait(min(wait, 1.0))
            runtime["wake"].clear()
            continue

        with runtime["lock"]:
            if not runtime["enabled"] or runtime["running"]:
                continue
            # Claim this deadline before worker execution. note_scan_started()
            # replaces it with the exact watchdog-acquisition cadence boundary.
            runtime["running"] = True
            runtime["next_due_monotonic"] = None

        ok = False
        error: object | None = None
        try:
            ok = bool(worker())
        except Exception as exc:  # worker owns detailed logging
            error = exc
        finally:
            with runtime["lock"]:
                runtime["running"] = False
                if runtime["enabled"] and runtime["next_due_monotonic"] is None:
                    # Watchdog collision/transient failure: retry soon. A normal
                    # successful worker calls note_scan_started() and already has
                    # the next deadline anchored to actual scan start.
                    _schedule_retry(
                        runtime,
                        5.0 if not ok else runtime["refresh_seconds"],
                        error,
                    )
            runtime["wake"].set()


def _reset_for_tests() -> None:
    """Reset the shared runtime without creating a second live scheduler thread."""
    runtime = _runtime()
    with runtime["lock"]:
        runtime["enabled"] = False
        runtime["running"] = False
        runtime["refresh_seconds"] = 60
        runtime["worker"] = None
        runtime["last_started_at"] = None
        runtime["last_finished_at"] = None
        runtime["next_due_monotonic"] = None
        runtime["last_error"] = None
        runtime["generation"] = 0
        runtime["process_state"].clear()
        thread = runtime.get("thread")
        if thread is None or not thread.is_alive():
            runtime["thread"] = None
    runtime["wake"].set()

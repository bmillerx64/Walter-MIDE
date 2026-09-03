"""GS351/GS361/GS372: isolate scheduled reruns without deadlocking stale sessions.

Walter's 60-second auto-scan cadence uses an explicit ``st.rerun`` from a timed
fragment. If that rerun fires while provider work is genuinely active, Streamlit
can tear down/re-enter the app while the scan is in flight.

GS361 extended that protection through a short post-scan render window. GS372
closes the recovery hole exposed in live September 3 testing: session-state flags
can remain stale after an interrupted rerun/deploy even though the process-wide
scan watchdog is idle. Suppressing the scheduler solely from those stale flags
prevents the full-app rerun that would reconcile them, freezing the last completed
scan until a manual browser refresh.

The process watchdog is now authoritative for active scan ownership. A recently
queued manual request is still protected briefly, but stale queued intent no
longer blocks the scheduler forever.

This changes only rerun scheduling/recovery and observability. It does not alter
discovery, market data, scoring, ranking, VWAP, SuperTrend, qualification, alerts,
execution, or orders.
"""
from __future__ import annotations

from datetime import datetime, timezone
import time

from .session_controls import (
    SCAN_REQUESTED_AT_KEY,
    SCAN_REQUESTED_KEY,
    SCAN_RUNNING_KEY,
)

LAST_RERUN_KEY = "_walter_last_explicit_rerun_monotonic"
SUPPRESSED_RERUNS_KEY = "_walter_suppressed_reruns"
LAST_SCAN_FINISHED_KEY = "_walter_last_scan_finished_epoch"
ALLOWED_RERUNS_KEY = "_walter_allowed_explicit_reruns"
LAST_ALLOWED_RERUN_AT_KEY = "_walter_last_allowed_explicit_rerun_utc"
LAST_ALLOWED_RERUN_SCOPE_KEY = "_walter_last_allowed_explicit_rerun_scope"
RERUN_COOLDOWN_SECONDS = 5.0
POST_SCAN_RERUN_COOLDOWN_SECONDS = 15.0
RECENT_SCAN_REQUEST_GUARD_SECONDS = 5.0


def rerun_suppression_reason(
    state,
    *,
    now: float | None = None,
    epoch_now: float | None = None,
    protect_post_scan: bool = False,
    process_scan_running: bool | None = None,
) -> str | None:
    """Return why an explicit app rerun should be deferred, if any.

    ``process_scan_running`` is optional to preserve the historical pure-function
    contract used by existing tests. Production passes the watchdog's actual lock
    state so stale Streamlit session flags can never deadlock recovery.
    """
    session_running = bool(state.get(SCAN_RUNNING_KEY, False))
    scan_requested = bool(state.get(SCAN_REQUESTED_KEY, False))

    if process_scan_running is None:
        # Historical/default behavior for direct callers and existing tests.
        if session_running:
            return "scan already running"
        if scan_requested:
            return "scan already requested"
    else:
        # The process-wide watchdog is authoritative for whether provider work is
        # actually active. A stale session ``scan_in_progress=True`` must not
        # suppress the full-app rerun that repairs session state.
        if bool(process_scan_running):
            return "scan already running"

        # A fresh manual button request can briefly coexist with the timed
        # fragment. Protect only that short handoff. If the request is old (or a
        # legacy/stale flag has no timestamp), allow the app rerun so the request
        # can be consumed or reconciled instead of freezing AutoScan indefinitely.
        if scan_requested:
            epoch_now = time.time() if epoch_now is None else float(epoch_now)
            try:
                requested_at = float(state.get(SCAN_REQUESTED_AT_KEY))
            except (TypeError, ValueError):
                requested_at = None
            if requested_at is not None:
                request_age = epoch_now - requested_at
                if 0 <= request_age < RECENT_SCAN_REQUEST_GUARD_SECONDS:
                    return "scan already requested"

    if protect_post_scan:
        epoch_now = time.time() if epoch_now is None else float(epoch_now)
        try:
            finished_at = float(state.get(LAST_SCAN_FINISHED_KEY))
        except (TypeError, ValueError):
            finished_at = None
        if finished_at is not None:
            since_finish = epoch_now - finished_at
            if 0 <= since_finish < POST_SCAN_RERUN_COOLDOWN_SECONDS:
                return "post-scan render cooldown"

    now = time.monotonic() if now is None else float(now)
    try:
        previous = float(state.get(LAST_RERUN_KEY))
    except (TypeError, ValueError):
        previous = None
    if previous is not None and now - previous < RERUN_COOLDOWN_SECONDS:
        return "rerun cooldown active"
    return None


def install() -> None:
    import streamlit as st
    from . import session_controls

    # Record when scan ownership is released. That moment is earlier than the end
    # of the Streamlit script, so it defines the small render window GS361 guards.
    current_finish = session_controls.finish_scan
    if not getattr(current_finish, "_gs361_post_scan_rerun_cooldown", False):
        def finish_scan_with_render_cooldown(state):
            current_finish(state)
            state[LAST_SCAN_FINISHED_KEY] = time.time()

        finish_scan_with_render_cooldown._gs361_post_scan_rerun_cooldown = True
        finish_scan_with_render_cooldown._gs351_original = current_finish
        session_controls.finish_scan = finish_scan_with_render_cooldown

    current = st.rerun
    if getattr(current, "_gs372_stale_session_recovery", False):
        return
    if getattr(current, "_gs351_session_rerun_isolation", False):
        # Warm Streamlit reloads can retain an older GS351/GS361 wrapper. Rebase
        # on its original Streamlit callable so the recovery logic is replaced,
        # not stacked behind a wrapper that can still suppress forever.
        current = getattr(current, "_gs351_original", current)

    def rerun_when_idle(*args, **kwargs):
        state = st.session_state
        now = time.monotonic()
        epoch_now = time.time()
        scope = str(kwargs.get("scope") or "")
        protect_post_scan = scope == "app"
        try:
            from .watchdog import PROCESS_SCAN_WATCHDOG

            process_scan_running = bool(PROCESS_SCAN_WATCHDOG.is_running)
        except Exception:
            # Fail conservatively if watchdog truth is unavailable.
            process_scan_running = None
        reason = rerun_suppression_reason(
            state,
            now=now,
            epoch_now=epoch_now,
            protect_post_scan=protect_post_scan,
            process_scan_running=process_scan_running,
        )
        if reason:
            state[SUPPRESSED_RERUNS_KEY] = int(state.get(SUPPRESSED_RERUNS_KEY, 0) or 0) + 1
            state["_walter_last_suppressed_rerun_reason"] = reason
            return None
        state[LAST_RERUN_KEY] = now
        state[ALLOWED_RERUNS_KEY] = int(state.get(ALLOWED_RERUNS_KEY, 0) or 0) + 1
        state[LAST_ALLOWED_RERUN_AT_KEY] = datetime.now(timezone.utc).isoformat()
        state[LAST_ALLOWED_RERUN_SCOPE_KEY] = scope or "default"
        return current(*args, **kwargs)

    rerun_when_idle._gs351_session_rerun_isolation = True
    rerun_when_idle._gs361_post_scan_rerun_cooldown = True
    rerun_when_idle._gs372_stale_session_recovery = True
    rerun_when_idle._gs351_original = current
    st.rerun = rerun_when_idle

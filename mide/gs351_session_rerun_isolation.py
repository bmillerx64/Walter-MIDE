"""GS351/GS361: prevent scheduled Streamlit reruns from colliding with active scans.

Walter's 60-second auto-scan cadence uses an explicit ``st.rerun`` from a timed
fragment. If that rerun fires while the current scan is still active (or while a
manual scan request is already queued), Streamlit can tear down/re-enter the app
while provider work is in flight. Live September 1 testing showed intermittent
browser ``CONNECTING`` states consistent with this collision pattern.

GS361 extends the same protection through the short post-scan render window. The
process watchdog clears ``scan_in_progress`` as soon as provider work finishes,
but Streamlit still has the rest of the page to render. A stale fragment tick can
otherwise request another full-app rerun in that gap. Only ``scope='app'`` reruns
are held for this short cooldown, so deploy/reconnect self-healing remains intact.

This patch changes only rerun scheduling and observability. It does not alter
discovery, market data, scoring, ranking, VWAP, SuperTrend, qualification, alerts,
execution, or orders.
"""
from __future__ import annotations

from datetime import datetime, timezone
import time

from .session_controls import SCAN_REQUESTED_KEY, SCAN_RUNNING_KEY

LAST_RERUN_KEY = "_walter_last_explicit_rerun_monotonic"
SUPPRESSED_RERUNS_KEY = "_walter_suppressed_reruns"
LAST_SCAN_FINISHED_KEY = "_walter_last_scan_finished_epoch"
ALLOWED_RERUNS_KEY = "_walter_allowed_explicit_reruns"
LAST_ALLOWED_RERUN_AT_KEY = "_walter_last_allowed_explicit_rerun_utc"
LAST_ALLOWED_RERUN_SCOPE_KEY = "_walter_last_allowed_explicit_rerun_scope"
RERUN_COOLDOWN_SECONDS = 5.0
POST_SCAN_RERUN_COOLDOWN_SECONDS = 15.0


def rerun_suppression_reason(
    state,
    *,
    now: float | None = None,
    epoch_now: float | None = None,
    protect_post_scan: bool = False,
) -> str | None:
    """Return why an explicit app rerun should be deferred, if any."""
    if bool(state.get(SCAN_RUNNING_KEY, False)):
        return "scan already running"
    if bool(state.get(SCAN_REQUESTED_KEY, False)):
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
    if getattr(current, "_gs351_session_rerun_isolation", False):
        return

    def rerun_when_idle(*args, **kwargs):
        state = st.session_state
        now = time.monotonic()
        epoch_now = time.time()
        # Walter's timed fragment is the only production caller using
        # scope='app'. Restrict post-scan suppression to that scheduler path so
        # GS341's reconnect self-heal (plain st.rerun()) is never blocked.
        scope = str(kwargs.get("scope") or "")
        protect_post_scan = scope == "app"
        reason = rerun_suppression_reason(
            state,
            now=now,
            epoch_now=epoch_now,
            protect_post_scan=protect_post_scan,
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
    rerun_when_idle._gs351_original = current
    st.rerun = rerun_when_idle

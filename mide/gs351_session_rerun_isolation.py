"""GS351: prevent scheduled Streamlit reruns from colliding with active scans.

Walter's 60-second auto-scan cadence uses an explicit ``st.rerun`` from a timed
fragment. If that rerun fires while the current scan is still active (or while a
manual scan request is already queued), Streamlit can tear down/re-enter the app
while provider work is in flight. Live September 1 testing showed intermittent
browser ``CONNECTING`` states consistent with this collision pattern.

This patch changes only rerun scheduling. It does not alter discovery, market data,
scoring, ranking, VWAP, SuperTrend, qualification, alerts, execution, or orders.
"""
from __future__ import annotations

from time import monotonic

from .session_controls import SCAN_REQUESTED_KEY, SCAN_RUNNING_KEY

LAST_RERUN_KEY = "_walter_last_explicit_rerun_monotonic"
SUPPRESSED_RERUNS_KEY = "_walter_suppressed_reruns"
RERUN_COOLDOWN_SECONDS = 5.0


def rerun_suppression_reason(state, *, now: float | None = None) -> str | None:
    """Return why an explicit app rerun should be deferred, if any."""
    if bool(state.get(SCAN_RUNNING_KEY, False)):
        return "scan already running"
    if bool(state.get(SCAN_REQUESTED_KEY, False)):
        return "scan already requested"
    now = monotonic() if now is None else float(now)
    try:
        previous = float(state.get(LAST_RERUN_KEY))
    except (TypeError, ValueError):
        previous = None
    if previous is not None and now - previous < RERUN_COOLDOWN_SECONDS:
        return "rerun cooldown active"
    return None


def install() -> None:
    import streamlit as st

    current = st.rerun
    if getattr(current, "_gs351_session_rerun_isolation", False):
        return

    def rerun_when_idle(*args, **kwargs):
        state = st.session_state
        now = monotonic()
        reason = rerun_suppression_reason(state, now=now)
        if reason:
            state[SUPPRESSED_RERUNS_KEY] = int(state.get(SUPPRESSED_RERUNS_KEY, 0) or 0) + 1
            state["_walter_last_suppressed_rerun_reason"] = reason
            return None
        state[LAST_RERUN_KEY] = now
        return current(*args, **kwargs)

    rerun_when_idle._gs351_session_rerun_isolation = True
    rerun_when_idle._gs351_original = current
    st.rerun = rerun_when_idle

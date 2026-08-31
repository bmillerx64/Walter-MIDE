"""GS341: self-heal a retained Streamlit session after a process deploy/restart.

Streamlit Community Cloud can reconnect an existing browser session to a newly
started Python process after a deploy. Walter already clears stale scan intent
on that boundary (GS313), but the browser can remain visually stuck until the
operator manually refreshes. This helper requests exactly one clean app rerun
once GS313 has safely reinitialized session controls in the new process.

Lifecycle only: no discovery, market-data, scoring, qualification, readiness,
ranking, thresholds, alerts, execution, or candidate-membership behavior changes.
"""
from __future__ import annotations

from collections.abc import MutableMapping


RECONNECT_RERUN_KEY = "_walter_reconnect_rerun_token"


def reconnect_rerun_needed(
    state: MutableMapping[str, object],
    *,
    prior_token: object,
    current_token: str,
    scan_running: bool | None,
) -> bool:
    """Return True exactly once for a safe cross-process browser reconnect."""
    process_changed = bool(prior_token) and prior_token != current_token
    if not process_changed or bool(scan_running):
        return False
    if state.get(RECONNECT_RERUN_KEY) == current_token:
        return False
    state[RECONNECT_RERUN_KEY] = current_token
    return True


def request_streamlit_rerun() -> None:
    """Request a clean app rerun without importing Streamlit at module import."""
    import streamlit as st

    st.rerun()

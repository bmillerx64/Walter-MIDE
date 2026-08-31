"""GS341: self-heal a retained Streamlit session after a process deploy/restart.

Streamlit Community Cloud can reconnect an existing browser session to a newly
started Python process after a deploy.  Walter already clears stale scan intent
on that boundary (GS313), but the browser can remain visually stuck until the
operator manually refreshes.  This patch performs one app rerun after session
controls have been safely reinitialized in the new process.

Lifecycle only: no discovery, market-data, scoring, qualification, readiness,
ranking, thresholds, alerts, execution, or candidate-membership behavior changes.
"""
from __future__ import annotations

from collections.abc import MutableMapping

from .gs313_restart_scan_guard import PROCESS_BOOT_TOKEN_KEY, current_process_boot_token


RECONNECT_RERUN_KEY = "_walter_reconnect_rerun_token"


def reconnect_rerun_needed(
    state: MutableMapping[str, object],
    *,
    prior_token: object,
    scan_running: bool | None,
) -> bool:
    """Return True exactly once for a safe cross-process browser reconnect."""
    current_token = current_process_boot_token()
    process_changed = bool(prior_token) and prior_token != current_token
    if not process_changed or bool(scan_running):
        return False
    if state.get(RECONNECT_RERUN_KEY) == current_token:
        return False
    state[RECONNECT_RERUN_KEY] = current_token
    return True


def install() -> None:
    """Wrap session initialization with a single deploy-boundary self-rerun."""
    from . import session_controls

    original = session_controls.initialize_session_controls
    if getattr(original, "_gs341_deploy_reconnect_self_heal", False):
        return

    def initialize_with_reconnect_self_heal(
        state,
        *,
        default_mode: str,
        scan_running: bool | None = None,
    ) -> None:
        prior_token = state.get(PROCESS_BOOT_TOKEN_KEY)
        original(
            state,
            default_mode=default_mode,
            scan_running=scan_running,
        )
        if not reconnect_rerun_needed(
            state,
            prior_token=prior_token,
            scan_running=scan_running,
        ):
            return

        # Import lazily so normal module import/test collection does not pull in
        # Streamlit.  st.rerun terminates this script pass and immediately starts
        # a clean one against the already-warm new process.
        import streamlit as st

        st.rerun()

    initialize_with_reconnect_self_heal._gs341_deploy_reconnect_self_heal = True
    session_controls.initialize_session_controls = initialize_with_reconnect_self_heal

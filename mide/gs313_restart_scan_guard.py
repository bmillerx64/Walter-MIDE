"""GS313: prevent stale scan intent from firing after a process restart.

Streamlit may reconnect a browser session to a newly deployed Python process while
retaining session state. A manual ``scan_requested`` flag is intentionally kept
across ordinary top-to-bottom reruns, but it must not survive a process restart:
that turns yesterday's/requested work into an unsolicited fresh scan.

This guard is lifecycle-only. It does not change discovery, market data, scoring,
qualification, readiness, ranking, alerts, thresholds, or execution.
"""
from __future__ import annotations

from uuid import uuid4


PROCESS_BOOT_TOKEN_KEY = "_walter_process_boot_token"
_PROCESS_BOOT_TOKEN = uuid4().hex


def current_process_boot_token() -> str:
    """Return this Python process's opaque lifecycle token."""
    return _PROCESS_BOOT_TOKEN


def install() -> None:
    """Wrap session initialization so stale cross-process scan intent is cleared."""
    from . import session_controls

    original = session_controls.initialize_session_controls
    if getattr(original, "_gs313_restart_scan_guard", False):
        return

    def initialize_with_restart_guard(
        state,
        *,
        default_mode: str,
        scan_running: bool | None = None,
    ) -> None:
        prior_token = state.get(PROCESS_BOOT_TOKEN_KEY)
        process_changed = bool(prior_token) and prior_token != _PROCESS_BOOT_TOKEN

        # A pending request is valid across an ordinary Streamlit rerun, but not
        # across a deployment/reboot into a different Python process. Never
        # discard intent while the process watchdog says a scan is actually live.
        if process_changed and not bool(scan_running):
            state[session_controls.SCAN_REQUESTED_KEY] = False
            state[session_controls.STOP_REQUESTED_KEY] = False

        state[PROCESS_BOOT_TOKEN_KEY] = _PROCESS_BOOT_TOKEN
        original(
            state,
            default_mode=default_mode,
            scan_running=scan_running,
        )

    initialize_with_restart_guard._gs313_restart_scan_guard = True
    session_controls.initialize_session_controls = initialize_with_restart_guard

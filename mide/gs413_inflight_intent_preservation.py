"""GS413 compatibility boundary for an already-active watchdog scan.

The process-wide AutoScan owner must suppress competing *idle* scheduler intent,
but it must not erase the request flag that represents a scan which is already
in flight.  Existing reboot/session stability relies on that distinction.
"""
from __future__ import annotations


def _inherit_gs_markers(wrapper, wrapped) -> None:
    for name, value in getattr(wrapped, "__dict__", {}).items():
        if name.startswith("_gs") and not hasattr(wrapper, name):
            setattr(wrapper, name, value)


def install() -> None:
    from . import session_controls

    current = session_controls.initialize_session_controls
    if getattr(current, "_gs413_inflight_intent_preservation", False):
        return

    def initialize_preserving_active_intent(
        state,
        *,
        default_mode: str,
        scan_running: bool | None = None,
    ) -> None:
        requested_before = bool(state.get(session_controls.SCAN_REQUESTED_KEY, False))
        requested_at_before = state.get(session_controls.SCAN_REQUESTED_AT_KEY)
        current(
            state,
            default_mode=default_mode,
            scan_running=scan_running,
        )
        if scan_running is True and requested_before:
            # An active process watchdog means this request may be the in-flight
            # scan itself. Do not reinterpret it as a competing idle AutoScan.
            # Passive sessions are still denied later by GS413's scheduler/view
            # authority once the app evaluates actual scheduling permission.
            state[session_controls.SCAN_REQUESTED_KEY] = True
            if requested_at_before is not None:
                state[session_controls.SCAN_REQUESTED_AT_KEY] = requested_at_before

    _inherit_gs_markers(initialize_preserving_active_intent, current)
    initialize_preserving_active_intent._gs413_inflight_intent_preservation = True
    initialize_preserving_active_intent._gs413_original = current
    session_controls.initialize_session_controls = initialize_preserving_active_intent

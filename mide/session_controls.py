"""Persistent Streamlit controls for provider selection and scan lifecycle."""

from __future__ import annotations

from collections.abc import MutableMapping
from typing import Any


DATA_MODE_KEY = "selected_data_mode"
PROVIDER_KEY = "selected_live_provider"
AUTO_SCAN_KEY = "auto_scan_enabled"
SCAN_RUNNING_KEY = "scan_in_progress"
SCAN_REQUESTED_KEY = "scan_requested"
STOP_REQUESTED_KEY = "scan_stop_requested"


def provider_for_mode(mode: str) -> str | None:
    """Return the provider represented by a live mode without a fallback."""
    if mode == "Live Alpaca":
        return "ALPACA"
    if mode == "Live Webull":
        return "WEBULL"
    return None


def initialize_session_controls(
    state: MutableMapping[str, Any], *, default_mode: str
) -> None:
    """Initialize persistent controls and discard interrupted scan activity.

    This function runs before any scan execution starts on each Streamlit script
    run.  A true value left behind by an interrupted prior run therefore cannot
    describe work executing in the current run and must not disable its controls.
    """
    state.setdefault(DATA_MODE_KEY, default_mode)
    state.setdefault(PROVIDER_KEY, provider_for_mode(state[DATA_MODE_KEY]))
    state.setdefault(AUTO_SCAN_KEY, True)
    state[SCAN_RUNNING_KEY] = False
    state.setdefault(SCAN_REQUESTED_KEY, False)
    state.setdefault(STOP_REQUESTED_KEY, False)


def select_data_mode(state: MutableMapping[str, Any]) -> None:
    """Persist an explicit data-mode widget change and its exact provider."""
    state[PROVIDER_KEY] = provider_for_mode(state[DATA_MODE_KEY])


def request_scan(state: MutableMapping[str, Any]) -> None:
    """Schedule a manual scan; execution becomes active only when it begins."""
    state[SCAN_REQUESTED_KEY] = True
    state[STOP_REQUESTED_KEY] = False


def request_stop(state: MutableMapping[str, Any]) -> None:
    """Immediately cancel this session's current and scheduled scans."""
    state[STOP_REQUESTED_KEY] = True
    state[SCAN_REQUESTED_KEY] = False
    state[SCAN_RUNNING_KEY] = False
    state[AUTO_SCAN_KEY] = False


def update_auto_scan(state: MutableMapping[str, Any]) -> None:
    """Apply an explicit auto-scan toggle without a rerun resetting it."""
    if state[AUTO_SCAN_KEY]:
        state[STOP_REQUESTED_KEY] = False


def begin_scheduled_scan(state: MutableMapping[str, Any]) -> None:
    """Record that an automatically scheduled scan has started."""
    state[SCAN_RUNNING_KEY] = True


def finish_scan(state: MutableMapping[str, Any]) -> None:
    """Clear transient scan activity without changing persistent controls."""
    state[SCAN_RUNNING_KEY] = False
    state[SCAN_REQUESTED_KEY] = False

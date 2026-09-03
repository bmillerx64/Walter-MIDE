"""Persistent Streamlit controls for provider selection and scan lifecycle."""

from __future__ import annotations

from collections.abc import MutableMapping
import time
from typing import Any


DATA_MODE_KEY = "selected_data_mode"
PROVIDER_KEY = "selected_live_provider"
AUTO_SCAN_KEY = "auto_scan_enabled"
SCAN_RUNNING_KEY = "scan_in_progress"
SCAN_REQUESTED_KEY = "scan_requested"
SCAN_REQUESTED_AT_KEY = "_walter_scan_requested_epoch"
STOP_REQUESTED_KEY = "scan_stop_requested"

VALID_DATA_MODES = {"Live Webull", "Demo"}


def provider_for_mode(mode: str) -> str | None:
    """Return the only supported live provider; legacy Alpaca state is inert."""
    if mode == "Live Webull":
        return "WEBULL"
    return None


def initialize_session_controls(
    state: MutableMapping[str, Any], *, default_mode: str, scan_running: bool | None = None
) -> None:
    """Initialize persistent controls and synchronize actual scan activity.

    The process watchdog is authoritative for whether a scan is actually active,
    but it must not erase a manual scan request that Streamlit just persisted on
    the widget-triggered rerun. Idle reconciliation therefore clears only stale
    stop intent; ``scan_requested`` remains set until scan execution consumes it
    or ``finish_scan`` clears it.
    """
    safe_default = default_mode if default_mode in VALID_DATA_MODES else "Demo"
    current_mode = state.get(DATA_MODE_KEY, safe_default)
    if current_mode not in VALID_DATA_MODES:
        current_mode = safe_default
    state[DATA_MODE_KEY] = current_mode
    state[PROVIDER_KEY] = provider_for_mode(current_mode)
    state.setdefault(AUTO_SCAN_KEY, False)

    if scan_running is None:
        state.setdefault(SCAN_RUNNING_KEY, False)
        state.setdefault(SCAN_REQUESTED_KEY, False)
        state.setdefault(STOP_REQUESTED_KEY, False)
        return

    state[SCAN_RUNNING_KEY] = bool(scan_running)
    state.setdefault(SCAN_REQUESTED_KEY, False)
    if scan_running:
        state.setdefault(STOP_REQUESTED_KEY, False)
    else:
        # Do not clear SCAN_REQUESTED_KEY here. A Streamlit button callback sets
        # it immediately before the top-to-bottom rerun, while the watchdog is
        # still correctly idle because execution has not begun yet.
        state[STOP_REQUESTED_KEY] = False


def select_data_mode(state: MutableMapping[str, Any]) -> None:
    """Persist a supported data-mode widget change and its exact provider."""
    mode = state.get(DATA_MODE_KEY)
    if mode not in VALID_DATA_MODES:
        state[DATA_MODE_KEY] = "Demo"
        mode = "Demo"
    state[PROVIDER_KEY] = provider_for_mode(mode)


def request_scan(state: MutableMapping[str, Any]) -> None:
    """Schedule a manual scan; execution becomes active only when it begins."""
    state[SCAN_REQUESTED_KEY] = True
    state[SCAN_REQUESTED_AT_KEY] = time.time()
    state[STOP_REQUESTED_KEY] = False


def request_stop(state: MutableMapping[str, Any]) -> None:
    """Immediately cancel this session's current and scheduled scans."""
    state[STOP_REQUESTED_KEY] = True
    state[SCAN_REQUESTED_KEY] = False
    state.pop(SCAN_REQUESTED_AT_KEY, None)
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
    state.pop(SCAN_REQUESTED_AT_KEY, None)

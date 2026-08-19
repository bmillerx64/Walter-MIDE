"""Regression contract for Streamlit reboot/session stability.

A fresh Streamlit websocket must not inherit transient scan intent from a stale
session snapshot. Persistent user choices remain untouched; only one-shot scan
lifecycle flags are repaired when the process watchdog says no scan is active.
"""

from mide.session_controls import (
    AUTO_SCAN_KEY,
    DATA_MODE_KEY,
    PROVIDER_KEY,
    SCAN_REQUESTED_KEY,
    STOP_REQUESTED_KEY,
    initialize_session_controls,
)


def test_fresh_idle_session_clears_stale_transient_scan_flags():
    state = {
        DATA_MODE_KEY: "Live Webull",
        PROVIDER_KEY: "WEBULL",
        AUTO_SCAN_KEY: False,
        SCAN_REQUESTED_KEY: True,
        STOP_REQUESTED_KEY: True,
    }

    initialize_session_controls(state, default_mode="Live Webull", scan_running=False)

    assert state[DATA_MODE_KEY] == "Live Webull"
    assert state[PROVIDER_KEY] == "WEBULL"
    assert state[AUTO_SCAN_KEY] is False
    assert state[SCAN_REQUESTED_KEY] is False
    assert state[STOP_REQUESTED_KEY] is False


def test_active_process_scan_does_not_repair_transient_flags_mid_scan():
    state = {
        DATA_MODE_KEY: "Live Webull",
        AUTO_SCAN_KEY: True,
        SCAN_REQUESTED_KEY: True,
        STOP_REQUESTED_KEY: False,
    }

    initialize_session_controls(state, default_mode="Live Webull", scan_running=True)

    assert state[AUTO_SCAN_KEY] is True
    assert state[SCAN_REQUESTED_KEY] is True
    assert state[STOP_REQUESTED_KEY] is False

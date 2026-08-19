from mide.session_controls import (
    AUTO_SCAN_KEY,
    DATA_MODE_KEY,
    PROVIDER_KEY,
    SCAN_REQUESTED_KEY,
    STOP_REQUESTED_KEY,
    initialize_session_controls,
)


def test_idle_watchdog_preserves_pending_scan_and_clears_stale_stop_state():
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
    # A pending manual request must survive the immediate Streamlit rerun so
    # the scan execution path can consume it. Only stale stop intent is reset.
    assert state[SCAN_REQUESTED_KEY] is True
    assert state[STOP_REQUESTED_KEY] is False


def test_active_watchdog_preserves_inflight_scan_intent():
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

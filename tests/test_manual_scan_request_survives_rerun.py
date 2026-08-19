from mide.session_controls import (
    AUTO_SCAN_KEY,
    DATA_MODE_KEY,
    PROVIDER_KEY,
    SCAN_REQUESTED_KEY,
    STOP_REQUESTED_KEY,
    initialize_session_controls,
    request_scan,
)


def test_manual_scan_request_survives_idle_watchdog_rerun():
    state = {
        DATA_MODE_KEY: "Live Webull",
        PROVIDER_KEY: "WEBULL",
        AUTO_SCAN_KEY: False,
        SCAN_REQUESTED_KEY: False,
        STOP_REQUESTED_KEY: False,
    }

    request_scan(state)
    assert state[SCAN_REQUESTED_KEY] is True

    initialize_session_controls(state, default_mode="Live Webull", scan_running=False)

    assert state[SCAN_REQUESTED_KEY] is True
    assert state[STOP_REQUESTED_KEY] is False
    assert state[PROVIDER_KEY] == "WEBULL"

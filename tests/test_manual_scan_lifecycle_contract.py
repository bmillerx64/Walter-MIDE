from mide.session_controls import (
    AUTO_SCAN_KEY,
    DATA_MODE_KEY,
    PROVIDER_KEY,
    SCAN_REQUESTED_KEY,
    SCAN_RUNNING_KEY,
    STOP_REQUESTED_KEY,
    begin_scheduled_scan,
    finish_scan,
    initialize_session_controls,
    request_scan,
    request_stop,
)


def _live_state():
    return {
        DATA_MODE_KEY: "Live Webull",
        PROVIDER_KEY: "WEBULL",
        AUTO_SCAN_KEY: False,
        SCAN_RUNNING_KEY: False,
        SCAN_REQUESTED_KEY: False,
        STOP_REQUESTED_KEY: False,
    }


def test_manual_request_survives_rerun_then_finishes_cleanly():
    state = _live_state()

    request_scan(state)
    initialize_session_controls(state, default_mode="Live Webull", scan_running=False)

    assert state[SCAN_REQUESTED_KEY] is True
    assert state[SCAN_RUNNING_KEY] is False
    assert state[PROVIDER_KEY] == "WEBULL"

    begin_scheduled_scan(state)
    assert state[SCAN_RUNNING_KEY] is True
    assert state[SCAN_REQUESTED_KEY] is True

    finish_scan(state)
    assert state[SCAN_RUNNING_KEY] is False
    assert state[SCAN_REQUESTED_KEY] is False
    assert state[STOP_REQUESTED_KEY] is False
    assert state[PROVIDER_KEY] == "WEBULL"


def test_stop_cancels_pending_manual_request_without_changing_provider():
    state = _live_state()

    request_scan(state)
    request_stop(state)

    assert state[SCAN_REQUESTED_KEY] is False
    assert state[SCAN_RUNNING_KEY] is False
    assert state[STOP_REQUESTED_KEY] is True
    assert state[AUTO_SCAN_KEY] is False
    assert state[DATA_MODE_KEY] == "Live Webull"
    assert state[PROVIDER_KEY] == "WEBULL"

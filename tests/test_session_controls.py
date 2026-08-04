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
    select_data_mode,
    update_auto_scan,
)


def test_live_webull_remains_selected_after_run_live_scan_and_rerun():
    state = {}
    initialize_session_controls(state, default_mode="Live Alpaca")
    state[DATA_MODE_KEY] = "Live Webull"
    select_data_mode(state)

    request_scan(state)
    finish_scan(state)
    initialize_session_controls(state, default_mode="Live Alpaca")

    assert state[DATA_MODE_KEY] == "Live Webull"
    assert state[PROVIDER_KEY] == "WEBULL"


def test_auto_scan_stays_off_across_reruns():
    state = {}
    initialize_session_controls(state, default_mode="Live Alpaca")
    state[AUTO_SCAN_KEY] = False

    initialize_session_controls(state, default_mode="Live Alpaca")

    assert state[AUTO_SCAN_KEY] is False


def test_explicitly_reenabling_auto_scan_clears_a_previous_stop():
    state = {}
    initialize_session_controls(state, default_mode="Live Alpaca")
    request_stop(state)
    state[AUTO_SCAN_KEY] = True

    update_auto_scan(state)

    assert state[AUTO_SCAN_KEY] is True
    assert state[STOP_REQUESTED_KEY] is False


def test_stop_immediately_cancels_an_active_scan_and_prevents_auto_restart():
    state = {}
    initialize_session_controls(state, default_mode="Live Webull")
    request_scan(state)
    begin_scheduled_scan(state)
    assert state[SCAN_RUNNING_KEY] is True

    request_stop(state)

    assert state[SCAN_RUNNING_KEY] is False
    assert state[SCAN_REQUESTED_KEY] is False
    assert state[STOP_REQUESTED_KEY] is True
    assert state[AUTO_SCAN_KEY] is False


def test_initialization_uses_watchdog_state_instead_of_stale_session_activity():
    state = {SCAN_RUNNING_KEY: True}

    initialize_session_controls(
        state, default_mode="Live Webull", scan_running=False
    )

    assert state[SCAN_RUNNING_KEY] is False


def test_streamlit_rerun_preserves_active_watchdog_scan_state():
    state = {}

    initialize_session_controls(
        state, default_mode="Live Webull", scan_running=True
    )
    initialize_session_controls(
        state, default_mode="Live Webull", scan_running=True
    )

    assert state[SCAN_RUNNING_KEY] is True


def test_manual_request_is_pending_until_scan_execution_actually_begins():
    state = {}
    initialize_session_controls(state, default_mode="Live Webull")

    request_scan(state)

    assert state[SCAN_REQUESTED_KEY] is True
    assert state[SCAN_RUNNING_KEY] is False

    begin_scheduled_scan(state)
    assert state[SCAN_RUNNING_KEY] is True


def test_reruns_never_silently_switch_the_selected_provider():
    state = {}
    initialize_session_controls(state, default_mode="Live Webull")
    state[DATA_MODE_KEY] = "Live Alpaca"
    select_data_mode(state)
    assert state[PROVIDER_KEY] == "ALPACA"

    for default in ("Live Webull", "Demo", "Live Alpaca"):
        initialize_session_controls(state, default_mode=default)

    assert state[DATA_MODE_KEY] == "Live Alpaca"
    assert state[PROVIDER_KEY] == "ALPACA"

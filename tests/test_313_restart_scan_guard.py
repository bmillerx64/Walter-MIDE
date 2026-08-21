from mide.gs313_restart_scan_guard import (
    PROCESS_BOOT_TOKEN_KEY,
    current_process_boot_token,
)
from mide.session_controls import (
    AUTO_SCAN_KEY,
    SCAN_REQUESTED_KEY,
    SCAN_RUNNING_KEY,
    STOP_REQUESTED_KEY,
    initialize_session_controls,
    request_scan,
)


def test_process_restart_clears_stale_pending_scan_when_watchdog_idle():
    state = {
        PROCESS_BOOT_TOKEN_KEY: "previous-process",
        AUTO_SCAN_KEY: False,
        SCAN_REQUESTED_KEY: True,
        STOP_REQUESTED_KEY: True,
    }

    initialize_session_controls(
        state,
        default_mode="Live Webull",
        scan_running=False,
    )

    assert state[PROCESS_BOOT_TOKEN_KEY] == current_process_boot_token()
    assert state[SCAN_REQUESTED_KEY] is False
    assert state[STOP_REQUESTED_KEY] is False
    assert state[AUTO_SCAN_KEY] is False
    assert state[SCAN_RUNNING_KEY] is False


def test_ordinary_streamlit_rerun_preserves_real_manual_request():
    state = {}
    initialize_session_controls(state, default_mode="Live Webull", scan_running=False)
    request_scan(state)

    initialize_session_controls(state, default_mode="Live Webull", scan_running=False)

    assert state[PROCESS_BOOT_TOKEN_KEY] == current_process_boot_token()
    assert state[SCAN_REQUESTED_KEY] is True
    assert state[SCAN_RUNNING_KEY] is False


def test_restart_does_not_erase_intent_for_a_scan_watchdog_already_running():
    state = {
        PROCESS_BOOT_TOKEN_KEY: "previous-process",
        AUTO_SCAN_KEY: True,
        SCAN_REQUESTED_KEY: True,
        STOP_REQUESTED_KEY: False,
    }

    initialize_session_controls(
        state,
        default_mode="Live Webull",
        scan_running=True,
    )

    assert state[PROCESS_BOOT_TOKEN_KEY] == current_process_boot_token()
    assert state[SCAN_REQUESTED_KEY] is True
    assert state[SCAN_RUNNING_KEY] is True
    assert state[AUTO_SCAN_KEY] is True


def test_first_session_initialization_does_not_misclassify_manual_intent_as_stale():
    state = {
        AUTO_SCAN_KEY: False,
        SCAN_REQUESTED_KEY: True,
        STOP_REQUESTED_KEY: False,
    }

    initialize_session_controls(
        state,
        default_mode="Live Webull",
        scan_running=False,
    )

    assert state[PROCESS_BOOT_TOKEN_KEY] == current_process_boot_token()
    assert state[SCAN_REQUESTED_KEY] is True

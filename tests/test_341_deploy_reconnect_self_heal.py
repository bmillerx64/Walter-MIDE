from mide.gs341_deploy_reconnect_self_heal import (
    RECONNECT_RERUN_KEY,
    reconnect_rerun_needed,
    request_streamlit_rerun,
)


def test_cross_process_idle_session_requests_one_clean_rerun():
    state = {}

    assert reconnect_rerun_needed(
        state,
        prior_token="old-process",
        current_token="new-process",
        scan_running=False,
    ) is True
    assert state[RECONNECT_RERUN_KEY] == "new-process"

    assert reconnect_rerun_needed(
        state,
        prior_token="old-process",
        current_token="new-process",
        scan_running=False,
    ) is False


def test_ordinary_rerun_does_not_trigger_reconnect_self_heal():
    state = {}

    assert reconnect_rerun_needed(
        state,
        prior_token="same-process",
        current_token="same-process",
        scan_running=False,
    ) is False
    assert RECONNECT_RERUN_KEY not in state


def test_first_session_has_no_false_deploy_boundary():
    state = {}

    assert reconnect_rerun_needed(
        state,
        prior_token=None,
        current_token="new-process",
        scan_running=False,
    ) is False


def test_running_scan_is_never_interrupted_for_reconnect_cleanup():
    state = {}

    assert reconnect_rerun_needed(
        state,
        prior_token="old-process",
        current_token="new-process",
        scan_running=True,
    ) is False
    assert RECONNECT_RERUN_KEY not in state


def test_non_streamlit_test_context_does_not_raise_or_rerun():
    assert request_streamlit_rerun() is False

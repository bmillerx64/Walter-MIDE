from mide import gs351_session_rerun_isolation as gs351
from mide import session_controls


def _state(**updates):
    state = {
        session_controls.SCAN_RUNNING_KEY: False,
        session_controls.SCAN_REQUESTED_KEY: False,
    }
    state.update(updates)
    return state


def test_stale_session_running_flag_does_not_block_recovery_rerun():
    state = _state(**{session_controls.SCAN_RUNNING_KEY: True})

    reason = gs351.rerun_suppression_reason(
        state,
        now=100.0,
        epoch_now=1_000.0,
        protect_post_scan=True,
        process_scan_running=False,
    )

    assert reason is None


def test_real_process_scan_still_blocks_scheduler_rerun():
    state = _state(**{session_controls.SCAN_RUNNING_KEY: False})

    reason = gs351.rerun_suppression_reason(
        state,
        now=100.0,
        epoch_now=1_000.0,
        protect_post_scan=True,
        process_scan_running=True,
    )

    assert reason == "scan already running"


def test_recent_manual_request_keeps_short_collision_guard():
    state = _state(
        **{
            session_controls.SCAN_REQUESTED_KEY: True,
            session_controls.SCAN_REQUESTED_AT_KEY: 998.0,
        }
    )

    reason = gs351.rerun_suppression_reason(
        state,
        now=100.0,
        epoch_now=1_000.0,
        protect_post_scan=False,
        process_scan_running=False,
    )

    assert reason == "scan already requested"


def test_stale_manual_request_cannot_deadlock_autoscan():
    state = _state(
        **{
            session_controls.SCAN_REQUESTED_KEY: True,
            session_controls.SCAN_REQUESTED_AT_KEY: 900.0,
        }
    )

    reason = gs351.rerun_suppression_reason(
        state,
        now=100.0,
        epoch_now=1_000.0,
        protect_post_scan=False,
        process_scan_running=False,
    )

    assert reason is None


def test_legacy_request_without_timestamp_is_allowed_to_reconcile():
    state = _state(**{session_controls.SCAN_REQUESTED_KEY: True})

    reason = gs351.rerun_suppression_reason(
        state,
        now=100.0,
        epoch_now=1_000.0,
        protect_post_scan=False,
        process_scan_running=False,
    )

    assert reason is None


def test_request_timestamp_is_cleared_when_scan_finishes_or_stops():
    state = {}
    session_controls.initialize_session_controls(
        state, default_mode="Live Webull", scan_running=False
    )
    session_controls.request_scan(state)
    assert session_controls.SCAN_REQUESTED_AT_KEY in state

    session_controls.finish_scan(state)
    assert session_controls.SCAN_REQUESTED_AT_KEY not in state

    session_controls.request_scan(state)
    session_controls.request_stop(state)
    assert session_controls.SCAN_REQUESTED_AT_KEY not in state

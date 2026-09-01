from mide import gs351_session_rerun_isolation as gs351
from mide.session_controls import SCAN_REQUESTED_KEY, SCAN_RUNNING_KEY


def test_active_scan_suppresses_explicit_rerun():
    state = {SCAN_RUNNING_KEY: True, SCAN_REQUESTED_KEY: False}
    assert gs351.rerun_suppression_reason(state, now=100.0) == "scan already running"


def test_queued_scan_suppresses_duplicate_rerun():
    state = {SCAN_RUNNING_KEY: False, SCAN_REQUESTED_KEY: True}
    assert gs351.rerun_suppression_reason(state, now=100.0) == "scan already requested"


def test_recent_rerun_is_debounced():
    state = {
        SCAN_RUNNING_KEY: False,
        SCAN_REQUESTED_KEY: False,
        gs351.LAST_RERUN_KEY: 98.0,
    }
    assert gs351.rerun_suppression_reason(state, now=100.0) == "rerun cooldown active"


def test_idle_session_allows_scheduled_rerun():
    state = {
        SCAN_RUNNING_KEY: False,
        SCAN_REQUESTED_KEY: False,
        gs351.LAST_RERUN_KEY: 90.0,
    }
    assert gs351.rerun_suppression_reason(state, now=100.0) is None

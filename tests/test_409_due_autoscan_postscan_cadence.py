from pathlib import Path

from mide import gs351_session_rerun_isolation as reruns
from mide import session_controls


def _state(**updates):
    state = {
        session_controls.SCAN_RUNNING_KEY: False,
        session_controls.SCAN_REQUESTED_KEY: False,
    }
    state.update(updates)
    return state


def test_due_autoscan_bypasses_only_post_scan_render_cooldown():
    # GS405 target geometry: a scan starts at 1000, finishes at 1055, and the
    # 60-second start-to-start deadline arrives at 1060. GS361's old 15-second
    # post-scan guard must not push the next start out to 1070+.
    state = _state(
        **{
            session_controls.SCAN_REQUESTED_KEY: True,
            reruns.LAST_SCAN_FINISHED_KEY: 1055.0,
        }
    )

    assert reruns.scheduled_autoscan_due(
        state, process_scan_running=False
    ) is True
    assert reruns.rerun_suppression_reason(
        state,
        now=200.0,
        epoch_now=1060.0,
        protect_post_scan=True,
        process_scan_running=False,
    ) is None


def test_ordinary_app_rerun_keeps_gs361_post_scan_protection():
    state = _state(**{reruns.LAST_SCAN_FINISHED_KEY: 1055.0})

    assert reruns.rerun_suppression_reason(
        state,
        now=200.0,
        epoch_now=1060.0,
        protect_post_scan=True,
        process_scan_running=False,
    ) == "post-scan render cooldown"


def test_fresh_manual_scan_request_does_not_gain_autoscan_bypass():
    state = _state(
        **{
            session_controls.SCAN_REQUESTED_KEY: True,
            session_controls.SCAN_REQUESTED_AT_KEY: 1059.0,
            reruns.LAST_SCAN_FINISHED_KEY: 1055.0,
        }
    )

    assert reruns.scheduled_autoscan_due(
        state, process_scan_running=False
    ) is False
    assert reruns.rerun_suppression_reason(
        state,
        now=200.0,
        epoch_now=1060.0,
        protect_post_scan=True,
        process_scan_running=False,
    ) == "scan already requested"


def test_active_process_watchdog_remains_absolute_no_overlap_authority():
    state = _state(**{session_controls.SCAN_REQUESTED_KEY: True})

    assert reruns.scheduled_autoscan_due(
        state, process_scan_running=True
    ) is False
    assert reruns.rerun_suppression_reason(
        state,
        now=200.0,
        epoch_now=1060.0,
        protect_post_scan=True,
        process_scan_running=True,
    ) == "scan already running"


def test_watchdog_truth_is_required_for_post_scan_bypass():
    state = _state(
        **{
            session_controls.SCAN_REQUESTED_KEY: True,
            reruns.LAST_SCAN_FINISHED_KEY: 1055.0,
        }
    )

    assert reruns.scheduled_autoscan_due(
        state, process_scan_running=None
    ) is False
    assert reruns.rerun_suppression_reason(
        state,
        now=200.0,
        epoch_now=1060.0,
        protect_post_scan=True,
        process_scan_running=None,
    ) == "scan already requested"


def test_live_scheduler_still_marks_due_autoscan_without_manual_timestamp():
    source = Path("app.py").read_text()
    start = source.index("def arm_live_clock_engine(")
    end = source.index("\ndef _run_live_pipeline(", start)
    scheduler = source[start:end]

    assert "autoscan_request_due(" in scheduler
    assert "st.session_state[SCAN_REQUESTED_KEY] = True" in scheduler
    assert "request_scan(st.session_state)" not in scheduler


def test_gs409_remains_runtime_scheduling_only():
    source = Path("mide/gs351_session_rerun_isolation.py").read_text()
    forbidden = (
        "qualified_for_entry =",
        "qualified_for_alert =",
        "participation_score =",
        "expansion_score =",
        "vwap_distance_pct =",
        "supertrend_bullish =",
        "opportunity_state =",
    )
    assert not any(token in source for token in forbidden)

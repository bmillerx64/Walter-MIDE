from pathlib import Path

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
    request_stop,
    update_auto_scan,
)


def test_autoscan_preference_survives_idle_streamlit_rerun():
    state = {
        DATA_MODE_KEY: "Live Webull",
        PROVIDER_KEY: "WEBULL",
        AUTO_SCAN_KEY: True,
        SCAN_REQUESTED_KEY: False,
        STOP_REQUESTED_KEY: False,
    }

    initialize_session_controls(state, default_mode="Live Webull", scan_running=False)

    assert state[DATA_MODE_KEY] == "Live Webull"
    assert state[PROVIDER_KEY] == "WEBULL"
    assert state[AUTO_SCAN_KEY] is True
    assert state[SCAN_REQUESTED_KEY] is False
    assert state[STOP_REQUESTED_KEY] is False


def test_autoscan_begin_and_finish_do_not_disable_future_scheduling():
    state = {
        DATA_MODE_KEY: "Live Webull",
        PROVIDER_KEY: "WEBULL",
        AUTO_SCAN_KEY: True,
        SCAN_REQUESTED_KEY: False,
        STOP_REQUESTED_KEY: False,
        SCAN_RUNNING_KEY: False,
    }

    begin_scheduled_scan(state)
    assert state[SCAN_RUNNING_KEY] is True
    assert state[AUTO_SCAN_KEY] is True

    finish_scan(state)
    assert state[SCAN_RUNNING_KEY] is False
    assert state[SCAN_REQUESTED_KEY] is False
    assert state[AUTO_SCAN_KEY] is True


def test_stop_scan_is_the_explicit_autoscan_kill_switch():
    state = {
        DATA_MODE_KEY: "Live Webull",
        PROVIDER_KEY: "WEBULL",
        AUTO_SCAN_KEY: True,
        SCAN_REQUESTED_KEY: True,
        STOP_REQUESTED_KEY: False,
        SCAN_RUNNING_KEY: True,
    }

    request_stop(state)

    assert state[AUTO_SCAN_KEY] is False
    assert state[SCAN_RUNNING_KEY] is False
    assert state[SCAN_REQUESTED_KEY] is False
    assert state[STOP_REQUESTED_KEY] is True


def test_reenabling_autoscan_clears_prior_stop_intent():
    state = {
        AUTO_SCAN_KEY: True,
        STOP_REQUESTED_KEY: True,
    }

    update_auto_scan(state)

    assert state[AUTO_SCAN_KEY] is True
    assert state[STOP_REQUESTED_KEY] is False


def test_autoscan_uses_session_preserving_streamlit_fragment_not_browser_reload():
    source = Path("app.py").read_text(encoding="utf-8")
    function_start = source.index("def arm_live_clock_engine(")
    function_end = source.index("\ndef _run_live_pipeline(", function_start)
    scheduler = source[function_start:function_end]

    assert "@st.fragment(run_every=timedelta(seconds=interval))" in scheduler
    assert 'st.rerun(scope="app")' in scheduler
    assert "location.reload(" not in scheduler
    assert "window.parent.location.reload(" not in scheduler


def test_autoscan_scheduler_requires_live_enabled_idle_and_due_state():
    source = Path("app.py").read_text(encoding="utf-8")
    start = source.index("    due = (")
    end = source.index("    should_scan =", start)
    due_block = source[start:end]

    assert 'mode.startswith("Live ")' in due_block
    assert "and auto_refresh" in due_block
    assert "and live_possible" in due_block
    assert "and not st.session_state.scan_in_progress" in due_block
    assert ">= settings.refresh_seconds" in due_block

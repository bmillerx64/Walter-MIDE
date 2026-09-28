from datetime import datetime, timedelta, timezone
from pathlib import Path

from mide.session_controls import (
    AUTO_SCAN_KEY,
    DATA_MODE_KEY,
    PROVIDER_KEY,
    SCAN_REQUESTED_KEY,
    SCAN_RUNNING_KEY,
    STOP_REQUESTED_KEY,
    autoscan_request_due,
    autoscan_wait_seconds,
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

    assert "scheduler_poll_seconds = min(max(1, int(interval)), 5)" in scheduler
    assert "@st.fragment(run_every=timedelta(seconds=scheduler_poll_seconds))" in scheduler
    assert 'st.rerun(scope="app")' in scheduler
    # Guard executable browser reload calls, not explanatory comments/docstrings.
    assert ".location.reload(" not in scheduler


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


def test_autoscan_success_wait_is_measured_from_scan_start():
    started = datetime(2026, 9, 9, 14, 30, 0, tzinfo=timezone.utc)
    completed = started + timedelta(seconds=55)

    assert autoscan_wait_seconds(
        60, completed, started, now=completed
    ) == 5


def test_autoscan_long_scan_restarts_as_soon_as_safely_possible():
    started = datetime(2026, 9, 9, 14, 30, 0, tzinfo=timezone.utc)
    completed = started + timedelta(seconds=67)

    assert autoscan_wait_seconds(
        60, completed, started, now=completed
    ) == 1
    assert autoscan_request_due(
        60, completed, started, now=completed
    ) is True


def test_autoscan_failure_keeps_existing_retry_backoff():
    last_success = datetime(2026, 9, 9, 14, 29, 0, tzinfo=timezone.utc)
    failed_attempt = datetime(2026, 9, 9, 14, 30, 0, tzinfo=timezone.utc)
    now = failed_attempt + timedelta(seconds=2)

    assert autoscan_wait_seconds(
        60, last_success, failed_attempt, retry_seconds=20, now=now
    ) == 20
    assert autoscan_request_due(
        60,
        last_success,
        failed_attempt,
        retry_seconds=20,
        now=failed_attempt + timedelta(seconds=19),
    ) is False
    assert autoscan_request_due(
        60,
        last_success,
        failed_attempt,
        retry_seconds=20,
        now=failed_attempt + timedelta(seconds=20),
    ) is True


def test_autoscan_success_request_does_not_fire_before_start_deadline():
    started = datetime(2026, 9, 9, 14, 30, 0, tzinfo=timezone.utc)
    completed = started + timedelta(seconds=50)

    assert autoscan_request_due(
        60, completed, started,
        now=started + timedelta(seconds=59, milliseconds=999),
    ) is False
    assert autoscan_request_due(
        60, completed, started, now=started + timedelta(seconds=60)
    ) is True


def test_live_clock_fragment_queues_scan_at_start_to_start_deadline():
    source = Path("app.py").read_text(encoding="utf-8")
    function_start = source.index("def arm_live_clock_engine(")
    function_end = source.index("\ndef _run_live_pipeline(", function_start)
    scheduler = source[function_start:function_end]

    assert "interval = autoscan_wait_seconds(" in scheduler
    assert "autoscan_request_due(" in scheduler
    assert "st.session_state[SCAN_REQUESTED_KEY] = True" in scheduler
    assert 'request_latch_key = "_walter_live_scan_requested_for"' in scheduler
    assert "request_baseline = (" in scheduler
    assert "scheduler_poll_seconds = min(max(1, int(interval)), 5)" in scheduler
    assert "if st.session_state.get(request_latch_key) == request_baseline:" in scheduler
    assert "st.session_state[request_latch_key] = request_baseline" in scheduler


def test_gs568_latch_prevents_duplicate_full_app_reruns_for_same_scan_baseline():
    source = Path("app.py").read_text(encoding="utf-8")
    start = source.index("def arm_live_clock_engine(")
    end = source.index("\ndef _run_live_pipeline(", start)
    scheduler = source[start:end]

    due = scheduler.index("if not autoscan_request_due(")
    duplicate_guard = scheduler.index(
        "if st.session_state.get(request_latch_key) == request_baseline:"
    )
    latch = scheduler.index("st.session_state[request_latch_key] = request_baseline")
    request = scheduler.index("st.session_state[SCAN_REQUESTED_KEY] = True")
    rerun = scheduler.index('st.rerun(scope="app")')

    assert due < duplicate_guard < latch < request < rerun


def test_gs568_scheduler_fix_remains_orchestration_only():
    source = Path("app.py").read_text(encoding="utf-8")
    start = source.index("def arm_live_clock_engine(")
    end = source.index("\ndef _run_live_pipeline(", start)
    scheduler = source[start:end]

    forbidden = (
        "qualified_for_entry",
        "qualified_for_alert",
        "participation_score",
        "expansion_score",
        "vwap_distance_pct",
        ".bars(",
        ".snapshots(",
        "place_order(",
        "submit_order(",
        ".location.reload(",
    )
    assert not any(token in scheduler for token in forbidden)


def test_gs571_clock_is_self_contained_in_visible_header_component():
    source = Path("app.py").read_text(encoding="utf-8")
    start = source.index("def render_mission_header_component(")
    end = source.index("\ndef _run_live_pipeline(", start)
    clock = source[start:end]

    assert "st.components.v1.html(component_html, height=300, scrolling=False)" in clock
    assert "document.getElementById('walter-market-time')" in clock
    assert "document.getElementById('walter-market-phase')" in clock
    assert "window.setInterval(update, 1000)" in clock
    assert "window.parent" not in clock


def test_gs571_clock_has_no_scan_or_full_app_rerun_authority():
    source = Path("app.py").read_text(encoding="utf-8")
    start = source.index("def render_mission_header_component(")
    end = source.index("\ndef _run_live_pipeline(", start)
    clock = source[start:end]

    assert "SCAN_REQUESTED_KEY" not in clock
    assert "st.rerun(" not in clock
    assert ".location.reload(" not in clock


def test_gs571_scheduler_remains_gs568_only():
    source = Path("app.py").read_text(encoding="utf-8")
    start = source.index("def arm_live_clock_engine(")
    end = source.index("\ndef render_mission_header_component(", start)
    scheduler = source[start:end]

    assert "@st.fragment(run_every=timedelta(seconds=scheduler_poll_seconds))" in scheduler
    assert "@st.fragment(run_every=timedelta(seconds=1))" not in scheduler
    assert "window.setInterval(" not in scheduler


def test_gs572_header_mounts_before_blocking_live_scan():
    source = Path("app.py").read_text(encoding="utf-8")

    render_call = source.index("render_prescan_header()")
    scan_gate = source.index(
        'if mode.startswith("Live ") and should_scan and not st.session_state[STOP_REQUESTED_KEY]:'
    )
    assert render_call < scan_gate


def test_gs572_prescan_header_is_presentation_only():
    source = Path("app.py").read_text(encoding="utf-8")
    start = source.index("def render_prescan_header() -> None:")
    end = source.index("\n\n# GS572:", start)
    block = source[start:end]

    assert "render_mission_header_component(" in block
    assert "mission_control_header_markup(" in block
    assert "st.rerun(" not in block
    assert "SCAN_REQUESTED_KEY" not in block
    assert "begin_scheduled_scan(" not in block
    assert "run_live(" not in block

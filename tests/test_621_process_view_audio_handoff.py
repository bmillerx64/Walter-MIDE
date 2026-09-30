from pathlib import Path


APP = Path("app.py")


def _source() -> str:
    return APP.read_text(encoding="utf-8")


def test_gs621_process_owned_reconnect_does_not_require_session_attempt():
    source = _source()

    assert """const recoveryBaselinePresent = processOwned
              ? processStartedAt > 0
              : attemptedAt > 0;""" in source
    assert """const recoveryDue = recoveryBaselinePresent
              && nativeStreamlitConnecting()""" in source

    # The old passive-observer deadlock condition must not survive.
    assert """const recoveryDue = attemptedAt > 0
              && nativeStreamlitConnecting()""" not in source


def test_gs621_state_surface_is_committed_before_semantic_speech():
    source = _source()

    state_render = source.index(
        "with mission_plan_slot:\n    render_walter_mission_control(actionable_records)"
    )
    state_detail = source.index(
        "with escalation_engine_slot:\n    render_escalation_engine(actionable_records)"
    )
    focus_publish = source.index("prepare_completed_scan_audio_focus(actionable_records)")
    semantic_play = source.index(
        'play_alert("assets/alert.wav", alert_phrase, alert_voice_for_session())'
    )

    assert state_render < state_detail < focus_publish < semantic_play


def test_gs621_routine_scan_audio_registration_precedes_heavy_radar_render():
    source = _source()

    registration = source.index(
        "[WALTER AUDIO] process scan browser registration"
    )
    radar_navigation = source.index('tab_names = [')
    opportunity_cards = source.index("opportunity_card(record)")
    catalyst_brief = source.index("def render_on_demand_catalyst_brief()")

    assert registration < radar_navigation < catalyst_brief < opportunity_cards


def test_gs621_keeps_exact_stale_audio_guards():
    source = _source()

    # A browser may recover more aggressively, but it may never speak an old
    # CompletedScan after a newer process scan has already started.
    assert "_process_audio_pending == _process_audio_current" in source
    assert "_process_audio_snapshot.last_started_at > completed_scan.completed_at" in source
    assert "newer_scan_started={_newer_process_scan_started}" in source
    assert "skipped stale completed scan before repaint" in source


def test_gs621_does_not_change_news_stream_installation():
    startup = Path("mide/startup.py").read_text(encoding="utf-8")

    assert "install_gs618()" in startup
    assert "install_gs620()" in startup
    assert startup.index("install_gs618()") < startup.index("install_gs620()")

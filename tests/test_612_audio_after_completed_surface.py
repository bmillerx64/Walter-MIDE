from pathlib import Path


def test_gs612_semantic_audio_runs_after_completed_opportunity_surface():
    source = Path("app.py").read_text(encoding="utf-8")

    surface = source.index(
        "# GS611: commit the two authoritative completed-scan operator surfaces"
    )
    mission = source.index("with mission_plan_slot:", surface)
    escalation = source.index("with escalation_engine_slot:", mission)
    gs612 = source.index(
        "# GS612: semantic voice must execute only after GS611 has committed"
    )
    focus = source.index("current_render_audio_focus(", gs612)
    event = source.index("current_render_audio_event(", focus)
    live_phrase = source.index("[WALTER AUDIO] canonical live phrase", event)
    process_heartbeat = source.index(
        "# GS601: consume process-scan audio only after the entire dashboard render",
        live_phrase,
    )

    assert surface < mission < escalation < gs612 < focus < event < live_phrase
    assert live_phrase < process_heartbeat


def test_gs612_preserves_stale_scan_and_exact_focus_guards():
    source = Path("app.py").read_text(encoding="utf-8")
    start = source.index(
        "# GS612: semantic voice must execute only after GS611 has committed"
    )
    end = source.index(
        "# GS601: consume process-scan audio only after the entire dashboard render",
        start,
    )
    block = source[start:end]

    assert "_audio_process_snapshot.last_started_at > completed_scan.completed_at" in block
    assert "semantic alert suppressed for stale visible scan" in block
    assert "expected_scan_token=_audio_scan_token" in block
    assert "play_alert(" in block
    assert "mark_render_audio_event_spoken" in block


def test_gs612_removed_pre_surface_semantic_audio_execution():
    source = Path("app.py").read_text(encoding="utf-8")

    radar_tabs = source.index("tab_names = [")
    surface = source.index(
        "# GS611: commit the two authoritative completed-scan operator surfaces"
    )
    assert "current_render_audio_event(" not in source[radar_tabs:surface]

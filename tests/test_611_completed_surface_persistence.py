from pathlib import Path


def test_gs611_completed_scan_surfaces_commit_once_after_completed_scan_handoff():
    source = Path("app.py").read_text(encoding="utf-8")

    prepare = source.index(
        "prepare_completed_scan_audio_focus(actionable_records)"
    )
    mission = source.index("with mission_plan_slot:")
    escalation = source.index("with escalation_engine_slot:")
    radar = source.index("tab_names = [")
    process_audio_boundary = source.index(
        "# GS601: consume process-scan audio only after the entire dashboard render"
    )

    assert source.count("with mission_plan_slot:") == 1
    assert source.count("with escalation_engine_slot:") == 1
    assert prepare < mission < radar < process_audio_boundary
    assert prepare < escalation < radar < process_audio_boundary


def test_gs611_process_clock_uses_live_fragment_not_static_full_render_overdue():
    source = Path("app.py").read_text(encoding="utf-8")

    fragment_start = source.index("def refresh_process_stage_indicator()")
    fragment_end = source.index("adopt_newer_process_scan()", fragment_start)
    fragment = source[fragment_start:fragment_end]
    assert "live_process_snapshot.running" in fragment
    assert "next_due_monotonic" in fragment
    assert "Process scan due" in fragment

    display_start = source.index("const remainingMs = deadline - now;")
    display_end = source.index("// GS576 transport failover.", display_start)
    display = source[display_start:display_end]
    assert "if (!processOwned)" in display
    assert "SCAN OVERDUE" in display
    assert "websocket" in display.lower()

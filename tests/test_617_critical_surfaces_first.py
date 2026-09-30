from pathlib import Path


def test_gs617_authoritative_surfaces_precede_all_radar_secondary_content():
    source = Path("app.py").read_text(encoding="utf-8")

    mission = source.index("with mission_plan_slot:")
    escalation = source.index("with escalation_engine_slot:")
    scanner_sections = source.index(
        "for section_name, section_records, expanded in scanner_v2_display_sections("
    )
    feed = source.index(
        "render_live_opportunity_feed(st.session_state.opportunity_feed_events)"
    )
    view = source.index('active_tab = st.radio(\n    "View"')
    sort_control = source.index('st.selectbox(\n        "Sort candidates by"')
    news = source.index("\n    render_on_demand_catalyst_brief()\n")

    assert mission < scanner_sections
    assert escalation < scanner_sections
    assert scanner_sections < feed < view < sort_control < news


def test_gs621_surface_commit_occurs_before_audio_validation_and_delivery():
    source = Path("app.py").read_text(encoding="utf-8")

    prepare = source.index(
        "prepare_completed_scan_audio_focus(actionable_records)"
    )
    stale_guard = source.index(
        "_audio_visible_scan_is_current = not (",
        prepare,
    )
    semantic_delivery = source.index(
        'play_alert("assets/alert.wav", alert_phrase',
        stale_guard,
    )
    mission = source.index("with mission_plan_slot:")
    escalation = source.index("with escalation_engine_slot:", mission)

    assert mission < escalation < prepare < stale_guard < semantic_delivery


def test_gs617_is_presentation_lifecycle_only():
    source = Path("app.py").read_text(encoding="utf-8")
    marker = source.index(
        "# GS621: commit the authoritative completed-scan State surfaces before any"
    )
    boundary = source.index("tab_names = [", marker)
    block = source[marker:boundary]

    forbidden = (
        "qualified_for_entry =",
        "qualified_for_alert =",
        "participation_score =",
        "expansion_score =",
        "request_scan(",
        "place_order(",
        "submit_order(",
    )
    assert not any(token in block for token in forbidden)

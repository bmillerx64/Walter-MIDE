from pathlib import Path


def test_gs615_radar_results_render_before_view_sort_and_news_controls():
    source = Path("app.py").read_text(encoding="utf-8")

    results = source.index(
        "for section_name, section_records, expanded in scanner_v2_display_sections("
    )
    view = source.index('active_tab = st.radio(\n    "View"')
    sort_control = source.index('st.selectbox(\n        "Sort candidates by"')
    news_call = source.index("\n    render_on_demand_catalyst_brief()\n")

    assert results < view < sort_control < news_call


def test_gs615_sort_state_is_read_before_results_without_changing_priority_default():
    source = Path("app.py").read_text(encoding="utf-8")

    persisted_sort = source.index(
        'radar_sort = str(st.session_state.get("radar_sort_mode") or "Walter Priority")'
    )
    results = source.index(
        "for section_name, section_records, expanded in scanner_v2_display_sections("
    )
    sort_widget = source.index('key="radar_sort_mode"')

    assert persisted_sort < results < sort_widget
    assert 'else trader_priority_sort_key' in source


def test_gs615_is_presentation_only():
    source = Path("app.py").read_text(encoding="utf-8")
    marker = source.index("# GS615: the trading Radar is results-first.")
    boundary = source.index('if active_tab == "Diagnostics":', marker)
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

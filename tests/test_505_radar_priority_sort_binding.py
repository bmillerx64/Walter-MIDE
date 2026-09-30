from pathlib import Path


def test_radar_walter_priority_sort_key_is_explicitly_bound():
    source = Path("app.py").read_text(encoding="utf-8")

    assert "from mide.trader_priority import trader_priority_sort_key" in source
    assert '("Walter Priority", "RS Score")' in source
    assert "else trader_priority_sort_key" in source


def test_radar_sort_binding_is_presentation_only():
    source = Path("app.py").read_text(encoding="utf-8")
    start = source.index(
        'radar_sort = str(st.session_state.get("radar_sort_mode") or "Walter Priority")'
    )
    end = source.index('if active_tab == "Diagnostics":', start)
    block = source[start:end]

    assert 'key="radar_sort_mode"' in block
    assert block.index("scanner_v2_display_sections(") < block.index(
        '"Sort candidates by"'
    )

    forbidden = (
        "qualified_for_entry =",
        "qualified_for_alert =",
        "qualified_for_watch =",
        "mission_rank =",
        "participation_score =",
        "expansion_score =",
        "place_order(",
        "submit_order(",
        "request_scan(",
    )
    assert not any(token in block for token in forbidden)

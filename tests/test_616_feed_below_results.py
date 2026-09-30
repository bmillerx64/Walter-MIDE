from pathlib import Path


def test_gs616_live_feed_slot_is_reserved_after_viable_results():
    source = Path("app.py").read_text(encoding="utf-8")

    results = source.index(
        "for section_name, section_records, expanded in scanner_v2_display_sections("
    )
    feed_slot = source.index("opportunity_feed_slot = st.empty()", results)
    feed_render = source.index(
        "render_live_opportunity_feed(st.session_state.opportunity_feed_events)",
        feed_slot,
    )
    view = source.index('active_tab = st.radio(\n    "View"', feed_render)

    assert results < feed_slot < feed_render < view


def test_gs616_no_top_level_feed_slot_remains_above_results():
    source = Path("app.py").read_text(encoding="utf-8")

    results = source.index(
        "for section_name, section_records, expanded in scanner_v2_display_sections("
    )
    assert "opportunity_feed_slot = st.empty()" not in source[:results]


def test_gs616_preserves_gs408_lazy_slot_contract():
    source = Path("mide/gs408_preserve_completed_scan_during_rerun.py").read_text(
        encoding="utf-8"
    )

    assert '"opportunity_feed_slot"' in source

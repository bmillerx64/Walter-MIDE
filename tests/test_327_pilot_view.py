from mide import ui
from mide import gs327_pilot_view as pilot


def test_pilot_view_is_installed():
    assert getattr(ui.mission_control_header_markup, "_gs327_pilot_view", False)
    assert getattr(ui.data_integrity_markup, "_gs327_pilot_view", False)
    assert getattr(ui.market_session_quality_markup, "_gs327_pilot_view", False)


def test_compact_header_keeps_operator_state_and_omits_funnel_detail():
    markup = pilot.compact_mission_header_markup(
        live=True,
        market_phase="Live Market",
        market_time="1:05 PM EDT",
        symbols_sampled=34,
        prefilter_count=13,
        candidate_count=4,
        focus_count=2,
        escalation_count=2,
        auto_scan="Every 60 sec",
        funnel_counts={"Universe": 34, "Price Gate": 18},
    )
    assert "34 scanned" in markup
    assert "4 candidates" in markup
    assert "2 focus" in markup
    assert "Every 60 sec" in markup
    assert "Architecture Funnel" not in markup
    assert "Price Gate" not in markup


def test_large_verification_panels_are_suppressed_from_radar_top():
    assert ui.data_integrity_markup({"status": "healthy"}) == ""
    assert ui.market_session_quality_markup([], snapshot_metrics={}) == ""


def test_original_diagnostic_renderers_remain_reachable_for_lower_surfaces():
    assert callable(ui.data_integrity_markup._gs327_original)
    assert callable(ui.market_session_quality_markup._gs327_original)
    assert callable(ui.mission_control_header_markup._gs327_original)

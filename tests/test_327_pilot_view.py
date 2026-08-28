from mide import ui
from mide import gs327_pilot_view as pilot


def test_pilot_view_hook_is_not_installed_by_default():
    assert not getattr(ui.mission_control_header_markup, "_gs327_pilot_view", False)
    assert not getattr(ui.mission_control_header_markup, "_gs328_scroll_repair", False)
    assert not getattr(ui.data_integrity_markup, "_gs328_scroll_repair", False)
    assert not getattr(ui.market_session_quality_markup, "_gs328_scroll_repair", False)


def test_original_radar_renderers_remain_active_after_rollback():
    trust = ui.data_integrity_markup(
        {
            "status": "HEALTHY SCAN",
            "trust_score": 100,
            "record_integrity_pct": 100,
            "freshness_pct": 100,
            "unique_symbols": 4,
            "record_count": 4,
            "status_reason": "Diagnostic only.",
        }
    )
    market = ui.market_session_quality_markup([])
    header = ui.mission_control_header_markup(
        live=True,
        market_phase="Live Market",
        market_time="1:05 PM EDT",
        symbols_sampled=34,
        prefilter_count=13,
        candidate_count=4,
        focus_count=2,
        escalation_count=2,
        auto_scan="Every 60 sec",
        funnel_counts={"universe": 34, "price": 18, "tradability": 20, "free_float": 13},
    )
    assert "SCAN TRUST" in trust
    assert "TODAY'S MARKET" in market
    assert "Walter • MIDE Radar" in header
    assert "Architecture Funnel" in header


def test_compact_pilot_renderer_remains_available_but_not_auto_installed():
    markup = pilot.compact_mission_header_markup(
        live=True,
        market_phase="Live Market",
        market_time="1:05 PM EDT",
        symbols_sampled=34,
        candidate_count=4,
        focus_count=2,
        escalation_count=2,
        auto_scan="Every 60 sec",
    )
    assert "34 scanned" in markup
    assert "4 candidates" in markup

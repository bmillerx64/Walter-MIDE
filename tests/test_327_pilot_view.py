from mide import ui
from mide import gs327_pilot_view as pilot


def test_pilot_view_is_installed():
    assert getattr(ui.mission_control_header_markup, "_gs327_pilot_view", False)
    assert getattr(ui.mission_control_header_markup, "_gs328_scroll_repair", False)
    assert getattr(ui.data_integrity_markup, "_gs328_scroll_repair", False)
    assert getattr(ui.market_session_quality_markup, "_gs328_scroll_repair", False)


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
    assert "display:none" not in markup


def test_streamlit_runtime_emits_no_hidden_verification_dom(monkeypatch):
    monkeypatch.setattr(pilot, "_in_streamlit_run", lambda: True)
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
        funnel_counts={"universe": 34, "price": 18},
    )
    assert trust == ""
    assert market == ""
    assert "34 scanned" in header
    assert "Architecture Funnel" not in header
    assert "display:none" not in header


def test_direct_renderer_calls_preserve_original_diagnostic_contracts(monkeypatch):
    monkeypatch.setattr(pilot, "_in_streamlit_run", lambda: False)
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
    assert "SCAN TRUST" in trust
    assert "TODAY'S MARKET" in market


def test_original_diagnostic_renderers_remain_reachable():
    assert callable(ui.data_integrity_markup._gs327_original)
    assert callable(ui.market_session_quality_markup._gs327_original)
    assert callable(ui.mission_control_header_markup._gs327_original)

from mide import gs330_compact_operator_status as compact
from mide import ui


def test_gs330_installs_visible_compact_wrappers():
    assert getattr(ui.mission_control_header_markup, "_gs330_compact_status", False)
    assert getattr(ui.data_integrity_markup, "_gs330_compact_status", False)
    assert getattr(ui.market_session_quality_markup, "_gs330_compact_status", False)


def test_live_compact_surfaces_remain_nonempty_and_visible(monkeypatch):
    monkeypatch.setattr(compact, "_in_streamlit_run", lambda: True)
    header = ui.mission_control_header_markup(
        live=True,
        market_phase="Live Market",
        market_time="2:40 PM EDT",
        symbols_sampled=33,
        prefilter_count=13,
        candidate_count=5,
        focus_count=2,
        escalation_count=2,
        auto_scan="Disabled",
        funnel_counts={"universe": 33, "price": 18},
    )
    trust = ui.data_integrity_markup(
        {
            "status": "HEALTHY SCAN",
            "trust_score": 100,
            "record_integrity_pct": 100,
            "freshness_pct": 100,
            "unique_symbols": 5,
            "record_count": 5,
        }
    )
    market = ui.market_session_quality_markup(
        [
            {
                "symbol": "TEST",
                "candidate_status": "Entry Ready",
                "participation_surge_score": 80,
                "expansion_quality": 70,
            }
        ]
    )
    for markup in (header, trust, market):
        assert markup
        assert "display:none" not in markup
        assert "height:0" not in markup
    assert "33 scanned" in header
    assert "Scan trust" in trust
    assert "confidence" in market


def test_direct_calls_keep_legacy_renderer_contracts(monkeypatch):
    monkeypatch.setattr(compact, "_in_streamlit_run", lambda: False)
    header = ui.mission_control_header_markup(
        live=True,
        market_phase="Live Market",
        market_time="2:40 PM EDT",
        symbols_sampled=33,
        prefilter_count=13,
        candidate_count=5,
        focus_count=2,
        escalation_count=2,
        auto_scan="Disabled",
        funnel_counts={"universe": 33, "price": 18},
    )
    trust = ui.data_integrity_markup(
        {
            "status": "HEALTHY SCAN",
            "trust_score": 100,
            "record_integrity_pct": 100,
            "freshness_pct": 100,
            "unique_symbols": 5,
            "record_count": 5,
            "status_reason": "All checks passed.",
        }
    )
    market = ui.market_session_quality_markup([])
    assert "Architecture Funnel" in header
    assert "SCAN TRUST" in trust
    assert "TODAY'S MARKET" in market


def test_compaction_does_not_touch_scanner_functions():
    assert callable(ui.mission_control_header_markup._gs330_original)
    assert callable(ui.data_integrity_markup._gs330_original)
    assert callable(ui.market_session_quality_markup._gs330_original)

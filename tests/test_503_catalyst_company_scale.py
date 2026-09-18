from pathlib import Path

from mide import gs503_catalyst_company_scale as gs503


def _paai_record():
    return {
        "symbol": "PAAI",
        "headline": "Company signs 10-year $1 billion agreement",
        "catalyst_magnitude": {
            "largest_stated_dollar_amount": 1_000_000_000,
            "stated_duration_years": 10,
            "contractual_language": True,
        },
        "catalyst_story": {
            "positive_attention_categories": ["CONTRACT_ORDER", "FINANCIAL_GROWTH"],
            "risk_categories": [],
            "quantities": [
                {"normalized_value": 1_000_000_000, "role": "DEAL_OR_BACKLOG"},
                {"normalized_value": 100_000_000, "role": "REVENUE"},
                {"normalized_value": 89_000_000, "role": "INVESTMENT_OR_FUNDING"},
            ],
        },
        "market_cap_reference": 25_000_000,
        "market_cap_source": "Webull native radar market_value",
    }


def test_paai_style_contract_is_company_scale_even_after_annualizing():
    detail = gs503.company_scale_context(_paai_record())

    assert detail["event_amount"] == 1_000_000_000
    assert detail["event_amount_role"] == "DEAL_OR_BACKLOG"
    assert detail["total_value_to_market_cap_ratio"] == 40.0
    assert detail["annualized_contract_value"] == 100_000_000
    assert detail["annualized_value_to_market_cap_ratio"] == 4.0
    assert detail["comparison_ratio_used"] == 4.0
    assert detail["relative_scale_band"] == "COMPANY_SCALE_OR_LARGER"
    assert "40x current $25M market cap" in detail["summary"]
    assert "$100M/yr = 4.0x market cap over 10y" in detail["summary"]
    assert detail["valuation_impact_inferred"] is False
    assert detail["trading_authority_changed"] is False


def test_large_offering_is_risk_scale_not_positive_catalyst():
    record = {
        "symbol": "RISK",
        "catalyst_magnitude": {
            "largest_stated_dollar_amount": 20_000_000,
            "stated_duration_years": None,
            "contractual_language": False,
        },
        "catalyst_story": {
            "positive_attention_categories": [],
            "risk_categories": ["DILUTION_RISK"],
            "quantities": [
                {"normalized_value": 20_000_000, "role": "DILUTION_OR_FINANCING"},
            ],
        },
        "market_cap_reference": 25_000_000,
    }

    detail = gs503.company_scale_context(record)

    assert detail["event_direction"] == "RISK_CONTEXT"
    assert detail["comparison_ratio_used"] == 0.8
    assert detail["relative_scale_band"] == "MAJOR_RELATIVE_SCALE"
    assert detail["summary"].startswith("Risk scale:")
    assert detail["profitability_inferred"] is False


def test_missing_market_cap_never_invents_company_scale():
    record = _paai_record()
    record.pop("market_cap_reference")

    detail = gs503.company_scale_context(record)

    assert detail["market_cap_available"] is False
    assert detail["relative_scale_band"] == "NOT_EVALUATED_NO_MARKET_CAP"
    assert detail["summary"] == ""


def test_snapshot_wrapper_uses_already_fetched_native_radar_market_value(monkeypatch):
    from mide.webull_live import LiveWebullProvider

    class Dummy:
        _native_radar_prices = {
            "ABC": {"market_value": 24_900_000, "price": 0.72},
        }

    baseline_calls = {"count": 0}

    def baseline(self, symbols):
        baseline_calls["count"] += 1
        return {"ABC": {"latestTrade": {"p": 0.72}}}

    monkeypatch.setattr(LiveWebullProvider, "snapshots", baseline)
    gs503._install_snapshot_reference()

    result = LiveWebullProvider.snapshots(Dummy(), ["ABC"])

    assert baseline_calls["count"] == 1
    assert result["ABC"]["market_cap_reference"] == 24_900_000
    assert result["ABC"]["market_cap_source"] == "Webull native radar market_value"


def test_prefilter_wrapper_carries_market_cap_without_changing_membership(monkeypatch):
    from mide import discovery

    def baseline(snapshots, settings):
        return [{"symbol": "ABC", "price": 1.0}]

    monkeypatch.setattr(discovery, "prefilter_snapshots", baseline)
    gs503._install_prefilter_reference()

    selected = discovery.prefilter_snapshots(
        {
            "ABC": {
                "latestTrade": {"p": 1.0},
                "market_cap_reference": 12_500_000,
                "market_cap_source": "Webull native radar market_value",
            }
        },
        object(),
    )

    assert [item["symbol"] for item in selected] == ["ABC"]
    assert selected[0]["market_cap_reference"] == 12_500_000


def test_analyze_wrapper_adds_context_without_changing_existing_scores(monkeypatch):
    from mide import discovery

    original = {
        **_paai_record(),
        "opportunity_score": 71,
        "participation_score": 52,
        "expansion_quality": 64,
        "mission_rank": 3,
        "qualified_for_entry": False,
    }

    def baseline(client, candidates, news_index, discovery_reasons):
        return [dict(original)]

    class Client:
        diagnostics = {}

    monkeypatch.setattr(discovery, "analyze_candidates", baseline)
    gs503._install_analyzed_context()

    records = discovery.analyze_candidates(
        Client(),
        [{"symbol": "PAAI", "market_cap_reference": 25_000_000}],
        {},
        {},
    )

    row = records[0]
    assert row["opportunity_score"] == 71
    assert row["participation_score"] == 52
    assert row["expansion_quality"] == 64
    assert row["mission_rank"] == 3
    assert row["qualified_for_entry"] is False
    assert row["catalyst_company_scale"]["relative_scale_band"] == "COMPANY_SCALE_OR_LARGER"
    assert Client.diagnostics["gs503_catalyst_company_scale"]["additional_provider_requests"] == 0
    assert Client.diagnostics["gs503_catalyst_company_scale"]["ranking_changed"] is False


def test_operator_catalyst_section_surfaces_relative_scale(monkeypatch):
    from mide import ui

    monkeypatch.setattr(ui, "_why_sections", lambda record: {"Catalyst": "10-year $1B agreement"})
    gs503._install_operator_presentation()

    record = {
        "catalyst_company_scale": gs503.company_scale_context(_paai_record()),
    }
    sections = ui._why_sections(record)

    assert "Company scale:" in sections["Catalyst"]
    assert "4.0x market cap" in sections["Catalyst"]


def test_startup_installs_gs503_after_benzinga_and_story_before_transport_observers():
    source = Path("mide/startup.py").read_text(encoding="utf-8")
    body = source.split("def ensure_late_runtime_installers() -> None:", 1)[1]

    assert "gs503_catalyst_company_scale" in source
    assert body.index("install_gs480()") < body.index("install_gs502()")
    assert body.index("install_gs502()") < body.index("install_gs503()") < body.index("install_gs481()")


def test_scope_lock_adds_context_only():
    source = Path("mide/gs503_catalyst_company_scale.py").read_text(encoding="utf-8")
    forbidden = (
        "qualified_for_entry =",
        "qualified_for_alert =",
        "qualified_for_watch =",
        "mission_rank =",
        "participation_score =",
        "expansion_score =",
        "opportunity_score =",
        "catalyst_score =",
        "vwap_distance_pct =",
        "supertrend_bullish =",
        "place_order(",
        "submit_order(",
        "play_alert(",
        "requests.get(",
    )
    assert not any(token in source for token in forbidden)
    assert "additional_provider_requests" in source
    assert "valuation_impact_inferred" in source

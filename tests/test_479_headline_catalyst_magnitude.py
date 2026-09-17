from __future__ import annotations

from pathlib import Path

from mide import discovery
from mide import gs315_news_intelligence as gs315
from mide import gs479_headline_catalyst_magnitude as gs479
from mide import ui


def test_paai_style_billion_dollar_multiyear_headline_is_preserved_as_facts():
    detail = gs479.headline_magnitude_context(
        "Roundtable secures 10-year, $1B agreement with Paradium.AI"
    )

    assert detail["headline_scale_band"] == "BILLION_PLUS"
    assert detail["largest_stated_dollar_amount"] == 1_000_000_000.0
    assert detail["stated_dollar_amounts"] == [1_000_000_000.0]
    assert detail["stated_duration_years"] == 10.0
    assert detail["contractual_language"] is True
    assert detail["summary"] == "$1B stated · 10-year term"
    assert detail["relative_company_scale"] == "NOT_EVALUATED_NO_COMPANY_BASELINE"
    assert detail["valuation_impact_inferred"] is False
    assert detail["closing_probability_inferred"] is False
    assert detail["trading_authority_changed"] is False


def test_multiple_disclosed_amounts_retain_all_values_and_largest_scale():
    detail = gs479.headline_magnitude_context(
        "Company signs 5-year $250 million contract with $40M initial order"
    )

    assert detail["headline_scale_band"] == "HUNDRED_MILLION_PLUS"
    assert detail["stated_dollar_amounts"] == [250_000_000.0, 40_000_000.0]
    assert detail["largest_stated_dollar_amount"] == 250_000_000.0
    assert detail["stated_duration_years"] == 5.0
    assert detail["summary"] == "$250M stated · 5-year term"


def test_word_form_dollars_are_understood_without_symbol():
    detail = gs479.headline_magnitude_context(
        "Company awarded 2.5 billion dollar infrastructure contract"
    )

    assert detail["headline_scale_band"] == "BILLION_PLUS"
    assert detail["largest_stated_dollar_amount"] == 2_500_000_000.0
    assert detail["summary"] == "$2.5B stated"


def test_generic_agreement_is_not_promoted_to_an_invented_scale():
    detail = gs479.headline_magnitude_context("Company announces strategic agreement")

    assert detail["headline_scale_band"] == "UNDISCLOSED"
    assert detail["largest_stated_dollar_amount"] is None
    assert detail["stated_duration_years"] is None
    assert detail["contractual_language"] is True
    assert detail["summary"] == ""


def test_gs315_metadata_gets_magnitude_without_changing_existing_classification(monkeypatch):
    def baseline(headline, **kwargs):
        return {
            "article_type": "DIRECT_CATALYST",
            "source_quality": "TRUSTED",
            "discovery_value": "HIGH",
            "catalyst_value": "HIGH",
            "age_minutes": 4.0,
        }

    monkeypatch.setattr(gs315, "classify_news_intelligence", baseline)
    gs479._install_gs315_metadata()

    result = gs315.classify_news_intelligence(
        "Roundtable secures 10-year, $1B agreement with Paradium.AI",
        source="Reuters",
    )

    assert result["article_type"] == "DIRECT_CATALYST"
    assert result["catalyst_value"] == "HIGH"
    assert result["catalyst_magnitude"]["headline_scale_band"] == "BILLION_PLUS"
    assert result["catalyst_magnitude"]["catalyst_score_changed"] is False


def test_analyzed_record_enrichment_is_copy_only_and_preserves_authority(monkeypatch):
    source = {
        "symbol": "PAAI",
        "headline": "Roundtable secures 10-year, $1B agreement with Paradium.AI",
        "catalyst_score": 8,
        "opportunity_score": 71.0,
        "conviction_score": 63.0,
        "qualified_for_entry": False,
        "qualified_for_alert": False,
    }

    def baseline(client, candidates, news_index, discovery_reasons):
        return [source]

    class Client:
        diagnostics = {}

    monkeypatch.setattr(discovery, "analyze_candidates", baseline)
    gs479._install_analyzed_records()
    result = discovery.analyze_candidates(Client(), [], {}, {})[0]

    assert result is not source
    assert "catalyst_magnitude" not in source
    assert result["catalyst_score"] == 8
    assert result["opportunity_score"] == 71.0
    assert result["conviction_score"] == 63.0
    assert result["qualified_for_entry"] is False
    assert result["qualified_for_alert"] is False
    assert result["catalyst_magnitude"]["summary"] == "$1B stated · 10-year term"


def test_operator_catalyst_section_adds_scale_context_without_replacing_headline(monkeypatch):
    headline = "Roundtable secures 10-year, $1B agreement with Paradium.AI"

    def baseline(record):
        return {"Catalyst": record["headline"], "Structure": "above VWAP"}

    monkeypatch.setattr(ui, "_why_sections", baseline)
    gs479._install_operator_presentation()
    record = {
        "headline": headline,
        "catalyst_magnitude": gs479.headline_magnitude_context(headline),
    }
    sections = ui._why_sections(record)

    assert sections["Catalyst"].startswith(headline)
    assert sections["Catalyst"].endswith("$1B stated · 10-year term")
    assert sections["Structure"] == "above VWAP"


def test_startup_binds_gs479_after_sparse_history_bridge_before_latency_recorder():
    source = Path("mide/startup.py").read_text(encoding="utf-8")
    assert "gs479_headline_catalyst_magnitude" in source
    body = source.split("def ensure_late_runtime_installers() -> None:", 1)[1]
    assert body.index("install_gs478()") < body.index("install_gs479()") < body.index("install_gs425()")


def test_gs479_scope_lock_is_context_only():
    source = Path("mide/gs479_headline_catalyst_magnitude.py").read_text(encoding="utf-8")
    forbidden = (
        "qualified_for_entry =",
        "qualified_for_alert =",
        "qualified_for_watch =",
        "catalyst_score =",
        "opportunity_score =",
        "conviction_score =",
        "execute_order",
        "place_order",
        "client.bars(",
        "client.snapshots(",
    )
    for token in forbidden:
        assert token not in source

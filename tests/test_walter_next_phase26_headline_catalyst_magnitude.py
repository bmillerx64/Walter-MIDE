"""Phase 26: GS479 headline catalyst magnitude follows authoritative ownership."""

from pathlib import Path

from mide import gs479_headline_catalyst_magnitude as gs479
from mide.authorities import discovery_news, presentation_audio


ROOT = Path(__file__).resolve().parents[1]


def test_gs479_fact_extraction_delegates_to_discovery_news():
    assert gs479.headline_magnitude_context is discovery_news.headline_magnitude_context
    assert gs479._dollar_amounts is discovery_news._headline_dollar_amounts
    assert gs479._duration_years is discovery_news._headline_duration_years
    assert gs479._scale_band is discovery_news._headline_scale_band
    assert gs479._format_money is discovery_news._headline_format_money


def test_gs479_installers_delegate_to_correct_authorities():
    assert (
        gs479._install_gs315_metadata
        is discovery_news.install_headline_magnitude_metadata
    )
    assert (
        gs479._install_analyzed_records
        is discovery_news.install_headline_magnitude_records
    )
    assert (
        gs479._install_operator_presentation
        is presentation_audio.install_headline_catalyst_magnitude_presentation
    )


def test_authoritative_headline_magnitude_contract_is_unchanged():
    detail = discovery_news.headline_magnitude_context(
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
    assert detail["catalyst_score_changed"] is False
    assert detail["trading_authority_changed"] is False


def test_gs479_source_is_compatibility_facade_not_duplicate_implementation():
    source = (ROOT / "mide/gs479_headline_catalyst_magnitude.py").read_text(
        encoding="utf-8"
    )

    assert "from mide.authorities import discovery_news as _news" in source
    assert "from mide.authorities import presentation_audio as _presentation" in source
    assert "def headline_magnitude_context(" not in source
    assert "def _install_gs315_metadata(" not in source
    assert "def _install_analyzed_records(" not in source
    assert "def _install_operator_presentation(" not in source


def test_phase26_scope_remains_context_only():
    source = (ROOT / "mide/gs479_headline_catalyst_magnitude.py").read_text(
        encoding="utf-8"
    )
    forbidden = (
        "qualified_for_entry =",
        "qualified_for_alert =",
        "qualified_for_watch =",
        "catalyst_score =",
        "opportunity_score =",
        "conviction_score =",
        "execute_order",
        "place_order",
        "submit_order",
        "client.bars(",
        "client.snapshots(",
        "requests.get(",
        "requests.post(",
    )
    assert not any(token in source for token in forbidden)

"""Phase 20: GS503 company-scale context is split by authoritative ownership."""

from __future__ import annotations

from pathlib import Path

from mide import gs503_catalyst_company_scale as gs503
from mide.authorities import market_evidence, presentation_audio


ROOT = Path(__file__).resolve().parents[1]


def _record():
    return {
        "symbol": "PAAI",
        "headline": "Company signs 10-year $1 billion agreement",
        "catalyst_magnitude": {
            "largest_stated_dollar_amount": 1_000_000_000,
            "stated_duration_years": 10,
            "contractual_language": True,
        },
        "catalyst_story": {
            "positive_attention_categories": ["CONTRACT_ORDER"],
            "risk_categories": [],
            "quantities": [
                {
                    "normalized_value": 1_000_000_000,
                    "role": "DEAL_OR_BACKLOG",
                },
            ],
        },
        "market_cap_reference": 25_000_000,
        "market_cap_source": "Webull native radar market_value",
    }


def test_gs503_factual_context_lives_in_market_evidence():
    assert gs503.company_scale_context is market_evidence.company_scale_context
    assert gs503._market_cap_reference is market_evidence.market_cap_reference
    assert (
        gs503._install_snapshot_reference
        is market_evidence.install_catalyst_scale_snapshot_reference
    )
    assert (
        gs503._install_prefilter_reference
        is market_evidence.install_catalyst_scale_prefilter_reference
    )
    assert (
        gs503._install_analyzed_context
        is market_evidence.install_catalyst_scale_analyzed_context
    )


def test_market_evidence_preserves_relative_scale_contract():
    detail = market_evidence.company_scale_context(_record())

    assert detail["event_amount"] == 1_000_000_000
    assert detail["total_value_to_market_cap_ratio"] == 40.0
    assert detail["annualized_value_to_market_cap_ratio"] == 4.0
    assert detail["relative_scale_band"] == "COMPANY_SCALE_OR_LARGER"
    assert "$100M/yr = 4.0x market cap over 10y" in detail["summary"]
    assert detail["trading_authority_changed"] is False


def test_presentation_audio_owns_company_scale_display_hook(monkeypatch):
    from mide import ui

    monkeypatch.setattr(
        ui,
        "_why_sections",
        lambda record: {"Catalyst": "10-year $1B agreement"},
    )
    presentation_audio.install_catalyst_company_scale_presentation()

    sections = ui._why_sections(
        {"catalyst_company_scale": market_evidence.company_scale_context(_record())}
    )

    assert "Company scale:" in sections["Catalyst"]
    assert "4.0x market cap" in sections["Catalyst"]


def test_gs503_source_is_compatibility_facade_not_duplicate_implementation():
    source = (ROOT / "mide/gs503_catalyst_company_scale.py").read_text(
        encoding="utf-8"
    )

    assert "from mide.authorities import market_evidence as _market" in source
    assert "from mide.authorities import presentation_audio as _presentation" in source
    assert "def company_scale_context(" not in source
    assert "def _install_snapshot_reference(" not in source
    assert "def _install_operator_presentation(" not in source


def test_phase20_scope_stays_context_only():
    forbidden = (
        "qualified_for_entry =",
        "qualified_for_alert =",
        "qualified_for_watch =",
        "mission_rank =",
        "participation_score =",
        "expansion_score =",
        "opportunity_score =",
        "catalyst_score =",
        "place_order(",
        "submit_order(",
        "play_alert(",
        "requests.get(",
    )
    for relative in (
        "mide/authorities/market_evidence.py",
        "mide/gs503_catalyst_company_scale.py",
    ):
        source = (ROOT / relative).read_text(encoding="utf-8")
        assert not any(token in source for token in forbidden)

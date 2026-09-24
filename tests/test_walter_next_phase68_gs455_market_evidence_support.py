"""Phase 68: GS455 progression support predicates belong to Market Evidence."""

from pathlib import Path
from types import SimpleNamespace

from mide import gs455_early_ignition_3m_confirmation as gs455
from mide.authorities import market_evidence


ROOT = Path(__file__).resolve().parents[1]


def test_phase68_halt_truth_is_preserved():
    assert market_evidence.progression_halted({"halted": True}) is True
    assert market_evidence.progression_halted(
        {"trading_status": "Trading suspended pending news"}
    ) is True
    assert market_evidence.progression_halted(
        {"trading_status": "ACTIVE"}
    ) is False


def test_phase68_current_attention_sources_are_preserved():
    assert market_evidence.progression_current_attention(
        {"discovery_reasons": ["Webull native: day_gainer"]}
    ) is True
    assert market_evidence.progression_current_attention(
        {"headline": "Material contract announced"}
    ) is True


def test_phase68_supporting_flow_thresholds_are_preserved():
    assert market_evidence.progression_supporting_flow(
        {"volume": 100_000}
    ) is True
    assert market_evidence.progression_supporting_flow(
        {"participation_surge_score": 20.0}
    ) is True
    assert market_evidence.progression_supporting_flow(
        {"expansion_quality": 40.0}
    ) is True
    assert market_evidence.progression_supporting_flow(
        {"volume_acceleration": 1.0}
    ) is True
    assert market_evidence.progression_supporting_flow(
        {"dollar_flow_acceleration_5m": 1.25}
    ) is True
    assert market_evidence.progression_supporting_flow({}) is False


def test_phase68_stale_market_evidence_generation_fails_closed(monkeypatch):
    monkeypatch.setattr(
        gs455,
        "_market_evidence",
        lambda: SimpleNamespace(),
    )
    assert gs455._halted({"symbol": "TEST"}) is True
    assert gs455._current_attention({"headline": "news"}) is False
    assert gs455._supporting_flow({"volume": 999_999}) is False


def test_phase68_legacy_helpers_are_lazy_market_evidence_facades():
    legacy = (
        ROOT / "mide/gs455_early_ignition_3m_confirmation.py"
    ).read_text(encoding="utf-8")
    authority = (
        ROOT / "mide/authorities/market_evidence.py"
    ).read_text(encoding="utf-8")

    for name in (
        "progression_halted",
        "progression_current_attention",
        "progression_supporting_flow",
    ):
        assert f"def {name}(" in authority

    start = legacy.index("def _halted(")
    end = legacy.index("def _timestamp(", start)
    facade = legacy[start:end]
    assert "_market_evidence()" in facade
    assert "participation_surge_score" not in facade
    assert "dollar_flow_acceleration_5m" not in facade
    assert "current_attention_provenance" not in facade
    assert "status_reason" not in facade


def test_phase68_adjacent_gs455_support_consumers_keep_historical_seam():
    gs457 = (
        ROOT / "mide/gs457_maturation_leader_priority.py"
    ).read_text(encoding="utf-8")
    gs460 = (
        ROOT / "mide/gs460_st_flip_compression_ignition.py"
    ).read_text(encoding="utf-8")
    assert "gs455._supporting_flow(record)" in gs457
    assert "gs455._supporting_flow(record)" in gs460


def test_phase68_scope_is_market_evidence_only():
    source = (
        ROOT / "mide/authorities/market_evidence.py"
    ).read_text(encoding="utf-8")
    start = source.index("# GS455 ordered ST/VWAP maturation progression evidence")
    end = source.index("# GS455 literal ST/VWAP line-cross enrichment", start)
    block = source[start:end]

    forbidden = (
        "qualified_for_entry =",
        "qualified_for_alert =",
        "qualified_for_watch =",
        "candidate_status =",
        "place_order(",
        "submit_order(",
        "escalation_alert_phrase",
        "LOOK NOW",
        ".get_bars(",
        ".history(",
    )
    assert not any(token in block for token in forbidden)

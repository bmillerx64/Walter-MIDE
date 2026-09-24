"""Phase 69: GS455 progression normalization belongs to Market Evidence."""

from datetime import timezone
from pathlib import Path
from types import SimpleNamespace

from mide import gs455_early_ignition_3m_confirmation as gs455
from mide.authorities import market_evidence


ROOT = Path(__file__).resolve().parents[1]


def test_phase69_numeric_normalization_preserves_first_finite_value():
    record = {
        "bad": "nan",
        "good": "12.5",
        "later": 99,
    }
    assert market_evidence.progression_number(
        record,
        "bad",
        "good",
        "later",
    ) == 12.5
    assert market_evidence.progression_number(
        {"value": "inf"},
        "value",
        default=7.0,
    ) == 7.0


def test_phase69_timestamp_normalization_preserves_iso_and_z_truth():
    parsed = market_evidence.progression_timestamp(
        "2026-09-15T10:39:00Z"
    )
    assert parsed is not None
    assert parsed.tzinfo == timezone.utc
    assert market_evidence.progression_timestamp("not-a-time") is None
    assert market_evidence.progression_timestamp(None) is None


def test_phase69_stale_market_evidence_generation_preserves_safe_normalization(monkeypatch):
    monkeypatch.setattr(
        gs455,
        "_market_evidence",
        lambda: SimpleNamespace(),
    )
    assert gs455._number(
        {"value": 12},
        "value",
        default=3.0,
    ) == 12.0
    stamp = gs455._timestamp(
        "2026-09-15T10:39:00-04:00"
    )
    assert stamp is not None
    assert stamp.isoformat() == "2026-09-15T10:39:00-04:00"


def test_phase69_legacy_normalizers_are_lazy_market_evidence_facades():
    legacy = (
        ROOT / "mide/gs455_early_ignition_3m_confirmation.py"
    ).read_text(encoding="utf-8")
    authority = (
        ROOT / "mide/authorities/market_evidence.py"
    ).read_text(encoding="utf-8")

    assert "def progression_number(" in authority
    assert "def progression_timestamp(" in authority

    number_start = legacy.index("def _number(")
    number_end = legacy.index("def _finite(", number_start)
    number_facade = legacy[number_start:number_end]
    assert "_market_evidence()" in number_facade
    assert '"progression_number"' in number_facade
    assert "_finite(record.get(key))" in number_facade

    stamp_start = legacy.index("def _timestamp(")
    stamp_end = legacy.index("def _thirty_second_rung(", stamp_start)
    stamp_facade = legacy[stamp_start:stamp_end]
    assert "_market_evidence()" in stamp_facade
    assert '"progression_timestamp"' in stamp_facade
    assert "Warm-deploy fallback" in stamp_facade


def test_phase69_authoritative_progression_block_uses_local_normalizers():
    source = (
        ROOT / "mide/authorities/market_evidence.py"
    ).read_text(encoding="utf-8")
    start = source.index("# GS455 ordered ST/VWAP maturation progression evidence")
    end = source.index("# GS455 literal ST/VWAP line-cross enrichment", start)
    block = source[start:end]

    assert "progression_number(" in block
    assert "progression_timestamp(" in block
    assert "gs455._number(" not in block
    assert "gs455._timestamp(" not in block


def test_phase69_scope_is_market_evidence_only():
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

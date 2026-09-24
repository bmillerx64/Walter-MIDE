"""Phase 72: GS456 literal 30s first-rung preference belongs to Market Evidence."""

from pathlib import Path
from types import SimpleNamespace

from mide import gs455_early_ignition_3m_confirmation as gs455
from mide import gs456_canonical_30s_vwap_cross as gs456
from mide.authorities import market_evidence


ROOT = Path(__file__).resolve().parents[1]


def test_phase72_literal_cross_outranks_tripwire_fallback():
    literal = {
        "timeframe": "30s",
        "crossed": True,
        "recent": True,
        "new": True,
        "timestamp": "2026-09-15T10:18:00-04:00",
        "age_seconds": 20.0,
        "current_confirmed": True,
    }

    result = market_evidence.canonical_30s_progression_rung(
        lambda _record: {
            "crossed": True,
            "kind": "tripwire",
        },
        {"st_vwap_30s_line_cross": literal},
    )

    assert result["kind"] == "literal_30s_st_vwap_line_cross"
    assert result["timestamp"] == "2026-09-15T10:18:00-04:00"


def test_phase72_alignment_literal_cross_is_supported():
    event = {
        "timeframe": "30s",
        "crossed": True,
        "current_confirmed": True,
    }
    result = market_evidence.canonical_30s_progression_rung(
        lambda _record: {"kind": "tripwire"},
        {
            "timeframe_alignment": {
                "30s": {
                    "st_vwap_line_cross": event,
                }
            }
        },
    )
    assert result["kind"] == "literal_30s_st_vwap_line_cross"


def test_phase72_fallback_preserves_original_rung_and_kind():
    result = market_evidence.canonical_30s_progression_rung(
        lambda _record: {
            "crossed": True,
            "current_confirmed": True,
        },
        {},
    )
    assert result["crossed"] is True
    assert result["kind"] == "canonical_30s_tripwire_flip_fallback"


def test_phase72_installer_preserves_historical_wrapper_markers(monkeypatch):
    def base_rung(_record):
        return {"crossed": False}

    monkeypatch.setattr(
        gs455,
        "_thirty_second_rung",
        base_rung,
    )
    market_evidence.install_canonical_30s_progression_rung()

    installed = gs455._thirty_second_rung
    assert getattr(
        installed,
        "_gs456_literal_30s_cross",
        False,
    )
    assert getattr(
        installed,
        "_gs456_original",
        None,
    ) is base_rung


def test_phase72_stale_market_evidence_generation_noops_installer(monkeypatch):
    monkeypatch.setattr(
        gs456,
        "_market_evidence",
        lambda: SimpleNamespace(),
    )
    assert gs456._install_gs455_first_rung() is None


def test_phase72_first_rung_meaning_lives_in_market_evidence():
    legacy = (
        ROOT / "mide/gs456_canonical_30s_vwap_cross.py"
    ).read_text(encoding="utf-8")
    authority = (
        ROOT / "mide/authorities/market_evidence.py"
    ).read_text(encoding="utf-8")

    assert "def canonical_30s_progression_rung(" in authority
    assert "def install_canonical_30s_progression_rung(" in authority

    start = legacy.index("def _install_gs455_first_rung(")
    end = legacy.index("def install(", start)
    facade = legacy[start:end]
    assert "st_vwap_30s_line_cross" not in facade
    assert "literal_30s_st_vwap_line_cross" not in facade
    assert "canonical_30s_tripwire_flip_fallback" not in facade


def test_phase72_scope_is_market_evidence_only():
    source = (
        ROOT / "mide/authorities/market_evidence.py"
    ).read_text(encoding="utf-8")
    start = source.index(
        "# GS456 canonical literal 30s cross preference for GS455 first rung"
    )
    end = source.index(
        "# GS455 ordered ST/VWAP maturation progression evidence",
        start,
    )
    block = source[start:end]

    forbidden = (
        "qualified_for_entry =",
        "qualified_for_watch =",
        "place_order(",
        "submit_order(",
        "request_scan(",
        ".get_bars(",
        ".history(",
    )
    assert not any(token in block for token in forbidden)

"""Phase 71: GS456 canonical 30s propagation belongs to Market Evidence."""

from pathlib import Path
from types import SimpleNamespace

from mide import gs397_canonical_30s_tripwire_truth as gs397
from mide import gs456_canonical_30s_vwap_cross as gs456
from mide.authorities import market_evidence


ROOT = Path(__file__).resolve().parents[1]


def test_phase71_primary_above_vwap_prefers_canonical_30s_values():
    def original(_record, _alignment, _tripwire):
        return False

    result = market_evidence.canonical_30s_primary_above_vwap(
        original,
        {"vwap_value": 9.0},
        {
            "vwap_truth_authority": gs456.AUTHORITY,
            "vwap_value": 1.00,
            "above_vwap": True,
        },
        {"latest_close": 1.10},
    )
    assert result is True


def test_phase71_canonicalization_carries_30s_truth_without_entry_change():
    event = {
        "timeframe": "30s",
        "crossed": True,
        "current_confirmed": True,
    }
    record = {
        "qualified_for_entry": False,
        "qualified_for_watch": False,
        "timeframe_alignment": {
            "30s": {
                "vwap_truth_authority": gs456.AUTHORITY,
                "vwap_value": 0.62,
                "vwap_anchor_mode": "EXTENDED_0400_ET",
                "vwap_anchor_time_et": "2026-09-15T04:00:00-04:00",
                "supertrend_value": 0.64,
                "st_vwap_line_cross": event,
            }
        },
        "timeframes": {},
    }

    updated = market_evidence.canonicalize_gs397_with_30s_vwap(
        lambda row: row,
        record,
    )
    assert updated["vwap_30s_value"] == 0.62
    assert updated["st_vwap_30s_line_cross"] == event
    assert updated["timeframes"]["30s"]["vwap_value"] == 0.62
    assert updated["qualified_for_entry"] is False
    assert updated["qualified_for_watch"] is False


def test_phase71_installer_preserves_historical_gs397_markers(monkeypatch):
    def base_above(record, alignment_30s, tripwire):
        return None

    def base_canonicalize(record):
        return record

    monkeypatch.setattr(
        gs397,
        "_primary_above_vwap",
        base_above,
    )
    monkeypatch.setattr(
        gs397,
        "canonicalize_record",
        base_canonicalize,
    )

    market_evidence.install_canonical_30s_gs397_propagation()

    assert getattr(
        gs397._primary_above_vwap,
        "_gs456_canonical_30s_vwap",
        False,
    )
    assert getattr(
        gs397.canonicalize_record,
        "_gs456_canonical_30s_vwap",
        False,
    )
    assert getattr(
        gs397._primary_above_vwap,
        "_gs456_original",
        None,
    ) is base_above
    assert getattr(
        gs397.canonicalize_record,
        "_gs456_original",
        None,
    ) is base_canonicalize


def test_phase71_stale_market_evidence_generation_noops_installer(monkeypatch):
    monkeypatch.setattr(
        gs456,
        "_market_evidence",
        lambda: SimpleNamespace(),
    )
    assert gs456._install_gs397_canonicalization() is None


def test_phase71_gs397_meaning_lives_in_market_evidence():
    legacy = (
        ROOT / "mide/gs456_canonical_30s_vwap_cross.py"
    ).read_text(encoding="utf-8")
    authority = (
        ROOT / "mide/authorities/market_evidence.py"
    ).read_text(encoding="utf-8")

    for name in (
        "canonical_30s_primary_above_vwap",
        "canonicalize_gs397_with_30s_vwap",
        "install_canonical_30s_gs397_propagation",
    ):
        assert f"def {name}(" in authority

    start = legacy.index("def _install_gs397_canonicalization(")
    end = legacy.index("def _install_gs455_first_rung(", start)
    facade = legacy[start:end]
    assert "vwap_30s_value" not in facade
    assert "st_vwap_30s_line_cross" not in facade
    assert "gs397._primary_above_vwap" not in facade


def test_phase71_scope_is_market_evidence_only():
    source = (
        ROOT / "mide/authorities/market_evidence.py"
    ).read_text(encoding="utf-8")
    start = source.index("# GS456 canonical 30s VWAP truth propagation into GS397")
    end = source.index("# GS455 ordered ST/VWAP maturation progression evidence", start)
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

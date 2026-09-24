"""Phase 70: GS456 30s alignment truth belongs to Market Evidence."""

from pathlib import Path
from types import SimpleNamespace

from mide import gs378_live_vwap_st_crossover as gs378
from mide import gs456_canonical_30s_vwap_cross as gs456
from mide.authorities import market_evidence


ROOT = Path(__file__).resolve().parents[1]


def test_phase70_empty_alignment_contract_is_preserved():
    empty = market_evidence.canonical_30s_empty_alignment()
    assert empty["above_vwap"] is False
    assert empty["supertrend_bullish"] is False
    assert empty["aligned"] is False
    assert empty["vwap_truth_authority"] == gs456.AUTHORITY
    assert empty["source"] == gs456.SOURCE
    assert empty["st_vwap_line_cross"]["timeframe"] == "30s"


def test_phase70_historical_alignment_names_delegate_to_market_evidence(monkeypatch):
    sentinel = {
        "above_vwap": True,
        "supertrend_bullish": True,
        "aligned": True,
    }
    monkeypatch.setattr(
        market_evidence,
        "canonical_30s_alignment_truth",
        lambda _frame: dict(sentinel),
    )
    assert gs456.alignment_30s_truth(None) == sentinel


def test_phase70_installer_preserves_historical_gs378_marker(monkeypatch):
    def base_summary(day_1m, primary_1m, frame_30s=None):
        return {"base": True}

    monkeypatch.setattr(
        gs378,
        "_alignment_summary",
        base_summary,
    )
    market_evidence.install_canonical_30s_alignment_truth()

    installed = gs378._alignment_summary
    assert getattr(
        installed,
        "_gs456_canonical_30s_vwap",
        False,
    )
    assert getattr(
        installed,
        "_gs456_original",
        None,
    ) is base_summary


def test_phase70_stale_market_evidence_generation_fails_closed(monkeypatch):
    monkeypatch.setattr(
        gs456,
        "_market_evidence",
        lambda: SimpleNamespace(),
    )
    empty = gs456.alignment_30s_truth(None)
    assert empty["aligned"] is False
    assert empty["vwap_truth_authority"] == gs456.AUTHORITY
    assert gs456._install_alignment_truth() is None


def test_phase70_alignment_meaning_lives_in_market_evidence():
    legacy = (
        ROOT / "mide/gs456_canonical_30s_vwap_cross.py"
    ).read_text(encoding="utf-8")
    authority = (
        ROOT / "mide/authorities/market_evidence.py"
    ).read_text(encoding="utf-8")

    for name in (
        "canonical_30s_empty_alignment",
        "canonical_30s_alignment_truth",
        "canonical_alignment_summary_with_30s_truth",
        "install_canonical_30s_alignment_truth",
    ):
        assert f"def {name}(" in authority

    start = legacy.index("def _market_evidence(")
    end = legacy.index("def _install_gs397_canonicalization(", start)
    facade = legacy[start:end]
    assert "primary_vwap_context(day)" not in facade
    assert "gs378.supertrend(" not in facade
    assert "maturation_line_cross_event(" not in facade


def test_phase70_scope_is_market_evidence_only():
    source = (
        ROOT / "mide/authorities/market_evidence.py"
    ).read_text(encoding="utf-8")
    start = source.index("# GS456 canonical 30s VWAP / SuperTrend alignment evidence")
    end = source.index("# GS455 ordered ST/VWAP maturation progression evidence", start)
    block = source[start:end]

    forbidden = (
        "qualified_for_entry =",
        "qualified_for_alert =",
        "qualified_for_watch =",
        "candidate_status =",
        "place_order(",
        "submit_order(",
        "escalation_alert_phrase",
        ".get_bars(",
        ".history(",
    )
    assert not any(token in block for token in forbidden)

from pathlib import Path

from mide import gs441_distinct_action_audio as gs441
from mide import gs442_alignment_ladder_truth as gs442
from mide import timeframe_alignment
from mide import ui


def _record() -> dict:
    return {
        "symbol": "TEST",
        "alignment_score": 2,
        "alignment_label": "Good",
        "timeframe_alignment": {
            "30s": {"aligned": False},
            "1m": {"aligned": True},
            "3m": {"aligned": True},
            # Deliberately opposite stale 5m evidence proves GS442 reads 3m.
            "5m": {"aligned": False},
        },
    }


def test_gs442_uses_canonical_30s_1m_3m_alignment_members():
    markup = gs442.canonical_alignment_markup(_record())

    assert "Alignment 2/3 · Good · ranking only" in markup
    assert "30s ✗" in markup
    assert "1m ✓" in markup
    assert "3m ✓" in markup
    assert "5m" not in markup


def test_gs442_matches_alignment_engine_timeframes_without_recomputing_score():
    assert timeframe_alignment.TIMEFRAMES == ("30s", "1m", "3m")
    assert gs442.ALIGNMENT_DISPLAY_TIMEFRAMES == timeframe_alignment.TIMEFRAMES

    record = _record()
    record["alignment_score"] = 1
    markup = gs442.canonical_alignment_markup(record)
    assert "Alignment 1/3" in markup
    # The display consumes the stored score and details; it does not recalculate them.
    assert "3m ✓" in markup


def test_gs442_empty_contract_matches_existing_alignment_markup():
    assert gs442.canonical_alignment_markup({}) == ""


def test_gs442_install_is_idempotent_and_patches_operator_card_helper():
    gs442.install()
    first = ui.alignment_markup
    gs442.install()

    assert ui.alignment_markup is first
    assert getattr(first, "_gs442_alignment_ladder_truth", False)
    assert "3m ✓" in first(_record())
    assert "5m" not in first(_record())


def test_gs442_is_chained_from_gs441_for_cold_and_warm_sessions():
    source = Path("mide/gs441_distinct_action_audio.py").read_text(encoding="utf-8")

    assert "from .gs442_alignment_ladder_truth import install as install_gs442" in source
    assert source.count("_install_gs442()") >= 2

    # Calling the already-installed GS441 path must still converge GS442.
    gs441.install()
    assert getattr(ui.alignment_markup, "_gs442_alignment_ladder_truth", False)


def test_gs442_scope_lock_is_presentation_only():
    source = Path("mide/gs442_alignment_ladder_truth.py").read_text(encoding="utf-8")
    forbidden = (
        "qualified_for_entry =",
        "qualified_for_alert =",
        "participation_score =",
        "expansion_score =",
        "vwap_distance_pct =",
        "supertrend_bullish =",
        "alignment_score =",
        "candidate_status =",
        "request_scan(",
        "place_order(",
    )
    assert not any(token in source for token in forbidden)

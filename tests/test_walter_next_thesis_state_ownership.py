"""Phase 4 ownership contract for Walter's base Thesis / State meaning."""

from pathlib import Path

from mide.authorities import thesis_state


def test_base_opportunity_state_meaning_lives_in_thesis_authority():
    authority = Path("mide/authorities/thesis_state.py").read_text(encoding="utf-8")
    legacy = Path("mide/gs310_unified_opportunity_state.py").read_text(encoding="utf-8")

    assert "def base_opportunity_state(" in authority
    assert "def opportunity_state(record: dict)" in authority
    assert "def opportunity_state(record: dict)" not in legacy
    assert "base_opportunity_state as opportunity_state" in legacy


def test_gs310_reexports_authoritative_state_constants():
    from mide import gs310_unified_opportunity_state as gs310

    assert gs310.LOOK_NOW == thesis_state.LOOK_NOW
    assert gs310.DEVELOPING == thesis_state.DEVELOPING
    assert gs310.WATCH_FOR_ENTRY == thesis_state.WATCH_FOR_ENTRY
    assert gs310.CHASE_WAIT == thesis_state.CHASE_WAIT
    assert gs310.HALTED == thesis_state.HALTED
    assert gs310.STATE_COLORS is thesis_state.STATE_COLORS


def test_authoritative_base_keeps_non_negotiable_halt_and_antichase_order():
    aligned = {
        "symbol": "BASE",
        "vwap_relation": "above",
        "vwap_distance_pct": 0.8,
        "supertrend_bullish": True,
        "participation_surge_score": 80,
        "expansion_quality": 65,
    }
    halted = dict(aligned, is_halted=True, vwap_distance_pct=8.0)
    extended = dict(aligned, vwap_distance_pct=4.5)

    assert thesis_state.base_opportunity_state(halted)["state"] == thesis_state.HALTED
    assert thesis_state.base_opportunity_state(extended)["state"] == thesis_state.CHASE_WAIT
    assert thesis_state.base_opportunity_state(aligned)["state"] == thesis_state.WATCH_FOR_ENTRY

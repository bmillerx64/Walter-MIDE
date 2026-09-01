from mide.gs344_emergence_convergence_engine import (
    EmergenceSnapshot,
    apply_emergence_marks,
    emergence_recommendation,
    emergence_signal,
    reset_emergence_memory,
)


def _snap(participation, expansion, volume, *, above=True, bullish=True, fast=False, seen=1.0):
    return EmergenceSnapshot(
        participation=participation,
        expansion=expansion,
        volume=volume,
        vwap_distance_pct=0.8 if above else -0.8,
        above_vwap=above,
        supertrend_bullish=bullish,
        fast_mover=fast,
        seen_at=seen,
    )


def _record(**overrides):
    row = {
        "symbol": "TEST",
        "vwap_distance_pct": 0.9,
        "supertrend_bullish": True,
        "participation_surge_score": 39,
        "expansion_quality": 55,
        "volume": 850_000,
        "sources": ["day_gainers"],
    }
    row.update(overrides)
    return row


def test_multi_scan_convergence_surfaces_watch_first():
    history = [
        _snap(24, 42, 400_000, seen=1.0),
        _snap(29, 47, 560_000, seen=61.0),
    ]
    ok, reason = emergence_signal(_record(), history)
    assert ok is True
    assert "improving" in reason
    cue = emergence_recommendation(_record(), history)
    assert cue["label"] == "EMERGING · WATCH FIRST"
    assert "not an entry call" in cue["guidance"].lower()


def test_below_vwap_and_extended_names_are_never_emergence_promoted():
    history = [_snap(24, 42, 400_000), _snap(30, 48, 550_000, seen=61.0)]
    assert emergence_signal(_record(vwap_distance_pct=-0.2), history) == (False, "below VWAP")
    assert emergence_signal(_record(vwap_distance_pct=3.2), history) == (False, "too extended")


def test_flat_scores_do_not_trigger_even_with_good_current_structure():
    history = [_snap(35, 52, 500_000), _snap(36, 53, 600_000, seen=61.0)]
    ok, reason = emergence_signal(_record(participation_surge_score=37, expansion_quality=54), history)
    assert ok is False
    assert reason == "scores not converging"


def test_new_five_minute_mover_can_supply_advancing_attention_confirmation():
    history = [
        _snap(24, 42, 900_000, fast=False),
        _snap(29, 47, 900_000, fast=False, seen=61.0),
    ]
    record = _record(
        participation_surge_score=38,
        expansion_quality=55,
        volume=900_000,
        sources=["five_minute_movers"],
        ranks={"five_minute_movers": 7},
    )
    ok, reason = emergence_signal(record, history)
    assert ok is True
    assert "5-minute movers" in reason


def test_apply_marks_requires_history_before_emergence():
    reset_emergence_memory()
    first = _record(participation_surge_score=24, expansion_quality=42, volume=400_000)
    second = _record(participation_surge_score=29, expansion_quality=47, volume=560_000)
    third = _record(participation_surge_score=39, expansion_quality=55, volume=850_000)

    assert "_gs344_emergence" not in apply_emergence_marks([first], now=1.0)[0]
    assert "_gs344_emergence" not in apply_emergence_marks([second], now=61.0)[0]
    marked = apply_emergence_marks([third], now=121.0)[0]
    assert marked["_gs344_emergence"]["label"] == "EMERGING · WATCH FIRST"


def test_weak_structure_is_not_promoted():
    history = [_snap(24, 42, 400_000), _snap(30, 48, 550_000, seen=61.0)]
    assert emergence_signal(_record(supertrend_bullish=False), history) == (False, "SuperTrend not bullish")
    assert emergence_signal(_record(participation_surge_score=20), history) == (False, "participation too weak")

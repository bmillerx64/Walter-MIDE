from mide.gs338_momentum_ignition_transition import (
    Snapshot,
    ignition_recommendation,
    momentum_ignition,
)


def _row(**overrides):
    row = {
        "symbol": "TEST",
        "vwap_distance_pct": 2.0,
        "vwap_relation": "above",
        "supertrend_bullish": True,
        "participation_score": 58,
        "expansion_score": 64,
        "volume": 2_000_000,
    }
    row.update(overrides)
    return row


def _prior(**overrides):
    values = {
        "participation": 45.0,
        "expansion": 54.0,
        "volume": 1_700_000.0,
        "vwap_distance_pct": 1.0,
        "supertrend_bullish": True,
        "seen_at": 100.0,
    }
    values.update(overrides)
    return Snapshot(**values)


def test_coot_like_transition_surfaces_before_chase_zone():
    row = _row(symbol="COOT", participation_score=58, expansion_score=64, vwap_distance_pct=2.4)
    igniting, reason = momentum_ignition(row, _prior(participation=44, expansion=52))
    assert igniting is True
    assert "participation" in reason
    recommendation = ignition_recommendation(row, _prior(participation=44, expansion=52))
    assert recommendation["label"] == "MOMENTUM IGNITING · LOOK NOW"


def test_already_extended_move_does_not_get_ignition_call():
    row = _row(vwap_distance_pct=8.0, participation_score=70, expansion_score=75)
    igniting, reason = momentum_ignition(row, _prior(participation=50, expansion=55))
    assert igniting is False
    assert reason == "already extended"


def test_static_good_scores_are_not_mislabeled_as_acceleration():
    row = _row(participation_score=60, expansion_score=62)
    igniting, reason = momentum_ignition(row, _prior(participation=58, expansion=60))
    assert igniting is False
    assert "no meaningful score acceleration" in reason


def test_below_vwap_never_gets_momentum_ignition():
    row = _row(vwap_distance_pct=-1.0, vwap_relation="below", participation_score=70, expansion_score=75)
    igniting, reason = momentum_ignition(row, _prior(participation=45, expansion=55))
    assert igniting is False
    assert reason == "not above VWAP"


def test_weak_participation_stays_non_actionable_even_if_expansion_jumps():
    row = _row(participation_score=32, expansion_score=70)
    igniting, reason = momentum_ignition(row, _prior(participation=22, expansion=50))
    assert igniting is False
    assert "participation still weak" in reason


def test_volume_regression_blocks_transition_cue():
    row = _row(participation_score=58, expansion_score=64, volume=1_000_000)
    igniting, reason = momentum_ignition(row, _prior(participation=44, expansion=52, volume=1_500_000))
    assert igniting is False
    assert reason == "volume evidence regressed"

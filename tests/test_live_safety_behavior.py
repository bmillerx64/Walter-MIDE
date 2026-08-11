from mide.live_safety import _behavioral_decision_with_participation_floor


def test_thin_participation_blocks_otherwise_technical_confluence():
    record = {
        "symbol": "THIN",
        "participation_score": 70,
        "rvol_proxy": 0.2,
        "volume_acceleration_1m": 1.1,
        "volume_acceleration_3m": 1.0,
        "dollar_flow_acceleration_1m": 1.0,
        "dollar_flow_acceleration_3m": 1.0,
        "structure_score": 85,
        "vwap_relation": "above",
        "vwap_distance_pct": 0.2,
        "supertrend_bullish": True,
        "momentum_quality_score": 80,
    }
    advanced, audit, confluence = _behavioral_decision_with_participation_floor(record)
    assert advanced is False
    assert confluence <= 45
    participation = next(step for step in audit if step["category"] == "Participation")
    assert participation["passed"] is False

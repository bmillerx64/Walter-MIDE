from copy import deepcopy

from mide.conviction import calculate_conviction
from mide.scanner_v2 import apply_scanner_v2


def record(**updates):
    value = {
        "symbol": "CVX", "price": 2.0, "pct_change": 5.0,
        "volume": 1_500_000, "dollar_volume": 3_000_000,
        "participation_score": 60, "participation_surge_score": 65,
        "volume_acceleration": 1.3, "timeframe_confirmations": 3,
        "supertrend_bullish": True, "ema65_relation": "above",
        "vwap_relation": "above", "vwap_distance_pct": 1.0,
        "higher_lows": True, "headline": "Contract awarded",
        "catalyst_score": 8, "opportunity_score_v2": 70, "trigger": "NO",
    }
    value.update(updates)
    return value


def test_conviction_is_deterministic_bounded_and_has_diagnostics():
    current = record()
    prior = record(volume=1_000_000, dollar_volume=2_000_000)
    first = calculate_conviction(current, prior)
    assert first == calculate_conviction(deepcopy(current), deepcopy(prior))
    assert 0 <= first["conviction_v2_score"] <= 100
    assert sum(first["conviction_components"].values()) == first["conviction_v2_score"]


def test_increasing_participation_raises_and_falling_participation_lowers_conviction():
    prior = record(participation_score=50, participation_surge_score=50, volume_acceleration=1.0)
    rising = calculate_conviction(record(participation_score=80, participation_surge_score=80, volume_acceleration=1.8), prior)
    falling = calculate_conviction(record(participation_score=25, participation_surge_score=25, volume_acceleration=.7), prior)
    assert rising["conviction_v2_score"] > falling["conviction_v2_score"]
    assert rising["conviction_trend"] == "Rising"
    assert falling["conviction_trend"] == "Falling"


def test_history_take_and_watching_reflect_current_state():
    prior = record(conviction_v2_score=42, conviction_history=[31, 36, 42])
    result = calculate_conviction(record(trigger="YES", vwap_relation="below", higher_lows=False), prior)
    assert result["conviction_history"][-1] == result["conviction_v2_score"]
    assert len(result["conviction_history"]) <= 5
    assert len([sentence for sentence in result["walter_take"].split(".") if sentence.strip()]) == 3
    assert "constructive" in result["walter_take"].lower() or "buyers" in result["walter_take"].lower() or "supporting" in result["walter_take"].lower()
    checks = {item["label"]: item["complete"] for item in result["walter_watching"]}
    assert checks["Fresh trigger"] is True
    assert checks["VWAP reclaimed"] is False
    assert checks["Pullback defended"] is False


def test_conviction_enrichment_does_not_change_workflow_or_entry_behavior(monkeypatch):
    import mide.scanner_v2 as scanner
    candidate = record(
        spread_pct=1.0, rvol_proxy=3.0, green_volume_ratio=1.3,
        supertrend_flip=True, near_hod=True, risk_flags=[],
        timeframes={"1m": {"above_vwap": True, "supertrend": True}, "3m": {"above_vwap": True, "supertrend": True}},
        reasons=[], cautions=[], discovery_reasons=["recent news"],
    )
    baseline = apply_scanner_v2([deepcopy(candidate)], {})[0]
    monkeypatch.setattr(scanner, "enrich_conviction", lambda value, prior: value)
    without = apply_scanner_v2([deepcopy(candidate)], {})[0]
    for key in ("candidate_status", "qualified_for_entry", "qualified_for_alert", "trigger", "alert_event"):
        assert baseline[key] == without[key]

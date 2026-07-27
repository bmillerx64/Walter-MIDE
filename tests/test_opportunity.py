from copy import deepcopy

from mide.opportunity import calculate_opportunity, enrich_opportunity
from mide.scanner_v2 import apply_scanner_v2


def record(**updates):
    value = {
        "symbol": "OPP",
        "participation_score": 60,
        "participation_surge_score": 65,
        "supertrend_bullish": True,
        "supertrend_flip": False,
        "ema65_relation": "above",
        "ema65_distance_pct": 0.2,
        "timeframe_confirmations": 3,
        "vwap_relation": "above",
        "vwap_distance_pct": 1.0,
        "higher_lows": True,
        "near_hod": False,
        "trigger": "NO",
        "dollar_volume": 2_000_000,
        "spread_pct": 1.0,
        "headline": "Company announces contract",
        "catalyst_score": 8,
        "news_age_hours": 2,
    }
    value.update(updates)
    return value


def test_opportunity_score_is_deterministic_and_bounded():
    candidate = record()
    assert calculate_opportunity(candidate) == calculate_opportunity(
        deepcopy(candidate)
    )
    for participation in (-100, 0, 50, 100, 1_000):
        score = calculate_opportunity(record(participation_score=participation))[
            "opportunity_score_v2"
        ]
        assert 0 <= score <= 100


def test_better_participation_increases_opportunity():
    low = calculate_opportunity(
        record(participation_score=10, participation_surge_score=10)
    )
    high = calculate_opportunity(
        record(participation_score=90, participation_surge_score=90)
    )
    assert high["opportunity_score_v2"] > low["opportunity_score_v2"]


def test_trigger_readiness_increases_opportunity():
    failed = [{"condition": str(i), "passed": False} for i in range(5)]
    passed = [{"condition": str(i), "passed": True} for i in range(5)]
    low = calculate_opportunity(record(trigger_diagnostics={"checks": failed}))
    high = calculate_opportunity(record(trigger_diagnostics={"checks": passed}))
    assert high["opportunity_score_v2"] > low["opportunity_score_v2"]


def test_material_extension_reduces_score_without_qualifying_or_removing():
    normal = calculate_opportunity(record(vwap_distance_pct=1.0))
    extended = calculate_opportunity(record(vwap_distance_pct=6.0))
    assert extended["opportunity_score_v2"] < normal["opportunity_score_v2"]
    assert "Extended" in extended["opportunity_blockers"][0]
    strengthening = record(vwap_distance_pct=6.0, candidate_status="Strengthening")
    enrich_opportunity(strengthening)
    assert strengthening["candidate_status"] == "Strengthening"


def test_opportunity_enrichment_does_not_change_entry_or_alert_behavior(monkeypatch):
    import mide.scanner_v2 as scanner

    candidate = {
        "symbol": "SAFE",
        "price": 1.0,
        "volume": 2_000_000,
        "dollar_volume": 2_000_000,
        "rvol_proxy": 3.0,
        "volume_acceleration": 1.5,
        "green_volume_ratio": 1.3,
        "pct_change": 8.0,
        "spread_pct": 1.0,
        "vwap_relation": "above",
        "vwap_distance_pct": 0.5,
        "supertrend_bullish": True,
        "supertrend_flip": True,
        "ema65_relation": "above",
        "ema65_distance_pct": 0.2,
        "higher_lows": True,
        "near_hod": True,
        "headline": "Contract award",
        "catalyst_score": 8,
        "news_age_hours": 1,
        "risk_flags": [],
        "timeframe_confirmations": 4,
        "timeframes": {
            "1m": {"above_vwap": True, "supertrend": True},
            "3m": {"above_vwap": True, "supertrend": True},
        },
        "reasons": [],
        "cautions": [],
    }
    baseline = apply_scanner_v2([deepcopy(candidate)], {})[0]
    monkeypatch.setattr(scanner, "enrich_opportunity", lambda value: value)
    without_engine = apply_scanner_v2([deepcopy(candidate)], {})[0]
    assert baseline["candidate_status"] == without_engine["candidate_status"]
    assert baseline["qualified_for_entry"] == without_engine["qualified_for_entry"]
    assert baseline["qualified_for_alert"] == without_engine["qualified_for_alert"]
    assert baseline["alert_event"] == without_engine["alert_event"]

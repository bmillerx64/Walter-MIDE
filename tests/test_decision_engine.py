from mide.decision_engine import IdentityPolicy, evaluate, stage2_filter
from mide.ui import decision_funnel_markup


def record(**changes):
    value = {
        "symbol": "EARN",
        "tradable": True,
        "status": "active",
        "price": 1.25,
        "float_shares": 2_000_000,
        "participation_score": 75,
        "dollar_volume": 2_000_000,
        "headline": "Company reports earnings",
        "structure_score": 75,
        "higher_lows": True,
        "vwap_relation": "above",
        "vwap_distance_pct": 0.4,
        "supertrend_bullish": True,
        "supertrend_distance_pct": 0.3,
        "current_momentum": 72,
        "volume_acceleration": 1.8,
    }
    value.update(changes)
    return value


def test_identity_filters_stop_in_exact_order_with_reason():
    result = evaluate([record(tradable=False, price=9, float_shares=20_000_000)])[0]
    assert result["current_stage"] == "Stage 2"
    assert [step["category"] for step in result["decision_funnel"]] == ["Universe", "Tradability"]
    assert result["decision_funnel"][-1]["result"] == "Non-tradable"


def test_float_limit_is_strict_and_auditable():
    rejected = evaluate([record(float_shares=3_500_001)])[0]
    assert rejected["final_decision"] == "Rejected"
    assert rejected["decision_funnel"][-1]["category"] == "Free Float"
    assert "Limit: 3.50M" in rejected["decision_funnel"][-1]["evidence"]


def test_free_float_diagnostic_logs_value_source_threshold_and_result(caplog):
    caplog.set_level("INFO", logger="mide.decision_engine")

    evaluate([record(symbol="NCRA", float_shares=1_300_000,
                     free_float_source="Polygon reference")])

    assert "Ticker: NCRA" in caplog.text
    assert "Price: PASS ($1.25)" in caplog.text
    assert "Value Returned: 1300000" in caplog.text
    assert "Source: Polygon reference" in caplog.text
    assert "Threshold: 3500000" in caplog.text
    assert "Result: PASS" in caplog.text


def test_free_float_diagnostic_logs_null_reason(caplog):
    caplog.set_level("INFO", logger="mide.decision_engine")

    evaluate([record(symbol="NCRA", float_shares=None)])

    assert "Ticker: NCRA" in caplog.text
    assert "Free Float Lookup:\nNULL" in caplog.text
    assert "Reason: No provider data" in caplog.text
    assert "Result: FAIL" in caplog.text


def test_stage_two_failure_never_reaches_stage_three_candidates():
    accepted, diagnostics, counts = stage2_filter([
        record(symbol="BDTX", float_shares=56_670_000),
        record(symbol="PASS", float_shares=3_500_000),
    ])

    assert [item["symbol"] for item in accepted] == ["PASS"]
    assert diagnostics == [{
        "symbol": "BDTX",
        "decision": "Rejected",
        "stage": "Stage 2",
        "reason": "Free Float",
        "result": "Exceeds limit",
        "evidence": ["Actual: 56.67M", "Limit: 3.50M"],
        "free_float": "56.67M",
        "maximum": "3.50M",
    }]
    assert counts == {
        "universe": 2,
        "tradability": 2,
        "price": 2,
        "free_float": 1,
        "free_float_evaluated": 2,
        "free_float_failed": 1,
        "free_float_lookup_failures": 0,
        "free_float_actual_failures": 1,
        "stage_3_analysis": 1,
    }


def test_stage_two_distinguishes_float_lookup_and_actual_failures():
    accepted, diagnostics, counts = stage2_filter([
        record(symbol="PASS"),
        record(symbol="LOOKUP", float_shares=None),
        record(symbol="TOOBIG", float_shares=9_000_000),
    ])

    assert [item["symbol"] for item in accepted] == ["PASS"]
    assert [item["result"] for item in diagnostics] == ["Unavailable", "Exceeds limit"]
    assert counts["free_float_evaluated"] == 3
    assert counts["free_float"] == 1
    assert counts["free_float_failed"] == 2
    assert counts["free_float_lookup_failures"] == 1
    assert counts["free_float_actual_failures"] == 1


def test_behavior_categories_are_independent_and_catalyst_is_not_scored():
    with_news, without_news = evaluate([record(), record(symbol="NONE", headline="")])
    assert with_news["confluence_score"] == without_news["confluence_score"] == 100
    assert [step["category"] for step in with_news["decision_funnel"][-7:]] == [
        "Participation", "Catalyst", "Price Structure", "VWAP", "SuperTrend",
        "Momentum Quality", "Confluence",
    ]
    assert without_news["decision_funnel"][5]["result"] == "No Catalyst"


def test_weak_participation_is_evidence_and_does_not_veto_confluence():
    accepted = evaluate([record(participation_score=10, volume_acceleration_3m=.8)])[0]
    assert accepted["current_stage"] == "Stage 4"
    assert accepted["final_decision"] == "Attention Earned"
    participation = next(s for s in accepted["decision_funnel"] if s["category"] == "Participation")
    assert participation["result"] == "10 — 3-minute volume flattening"
    assert not participation["passed"]


def test_policy_is_configurable():
    accepted = evaluate([record(price=8, float_shares=8_000_000)], IdentityPolicy(max_price=10, max_free_float=10_000_000))[0]
    assert accepted["eligible"] is True


def test_funnel_markup_exposes_current_stage_final_decision_and_reason():
    rejected = evaluate([record(float_shares=9_000_000)])[0]
    markup = decision_funnel_markup(rejected)
    assert "Stage 1 ↓ Stage 2 ↓ Stage 3 ↓ Current Stage ↓ Final Decision" in markup
    assert "Free Float" in markup
    assert "Current Stage:</b> Stage 2" in markup
    assert "Final Decision:</b> Rejected" in markup

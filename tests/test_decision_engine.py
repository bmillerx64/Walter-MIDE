from mide.decision_engine import IdentityPolicy, evaluate
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


def test_behavior_categories_are_independent_and_catalyst_is_not_scored():
    with_news, without_news = evaluate([record(), record(symbol="NONE", headline="")])
    assert with_news["confluence_score"] == without_news["confluence_score"] == 100
    assert [step["category"] for step in with_news["decision_funnel"][-7:]] == [
        "Participation", "Catalyst", "Price Structure", "VWAP", "SuperTrend",
        "Momentum Quality", "Confluence",
    ]
    assert without_news["decision_funnel"][5]["result"] == "No Catalyst"


def test_weak_participation_rejects_at_stage_three_with_explanation():
    rejected = evaluate([record(participation_score=10)])[0]
    assert rejected["current_stage"] == "Stage 3"
    assert rejected["final_decision"] == "Rejected"
    participation = next(s for s in rejected["decision_funnel"] if s["category"] == "Participation")
    assert participation["result"] == "Weak"
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

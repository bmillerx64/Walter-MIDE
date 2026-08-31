from mide.gs336_early_session_reset_watch import (
    actionable_attention_floor,
    guard_actionable_recommendation,
)


def _row(**overrides):
    row = {
        "symbol": "TEST",
        "vwap_distance_pct": 1.0,
        "vwap_relation": "above",
        "supertrend_bullish": True,
        "participation_score": 60,
        "expansion_score": 60,
        "volume": 1_000_000,
        "dollar_volume": 500_000,
        "headline": "Fresh company update",
    }
    row.update(overrides)
    return row


def _look_now(symbol="TEST"):
    return {
        "symbol": symbol,
        "label": "LOOK NOW",
        "message": "Current attention trigger.",
        "guidance": "Open the chart.",
    }


def test_below_vwap_can_never_present_as_look_now():
    row = _row(vwap_distance_pct=-3.0, vwap_relation="below")
    guarded = guard_actionable_recommendation(row, _look_now())
    assert guarded["label"] == "MONITOR · EVIDENCE BUILDING"
    assert "below VWAP" in guarded["message"]


def test_sora_like_weak_participation_is_monitor_not_look_now():
    row = _row(
        symbol="SORA",
        participation_score=14,
        expansion_score=47,
        volume=64_420,
        dollar_volume=121_000,
        headline="",
    )
    passed, reason = actionable_attention_floor(row)
    assert passed is False
    assert "participation" in reason
    guarded = guard_actionable_recommendation(row, _look_now("SORA"))
    assert guarded["label"] == "MONITOR · EVIDENCE BUILDING"


def test_cvkd_like_real_participation_and_expansion_keeps_look_now():
    row = _row(
        symbol="CVKD",
        participation_score=53,
        expansion_score=61,
        volume=2_970_000,
        dollar_volume=6_100_000,
        headline="Cadrenal Therapeutics advances CAD-1005 Phase 3 pathway",
    )
    guarded = guard_actionable_recommendation(row, _look_now("CVKD"))
    assert guarded["label"] == "LOOK NOW"


def test_light_volume_without_catalyst_requires_stronger_scores():
    row = _row(
        participation_score=45,
        expansion_score=52,
        volume=80_000,
        dollar_volume=120_000,
        headline="",
    )
    passed, reason = actionable_attention_floor(row)
    assert passed is False
    assert "volume" in reason


def test_non_look_now_recommendations_are_untouched():
    original = {
        "symbol": "COOT",
        "label": "CHASE / WAIT",
        "message": "Move is extended.",
        "guidance": "Wait for reset.",
    }
    assert guard_actionable_recommendation(_row(), original) is original

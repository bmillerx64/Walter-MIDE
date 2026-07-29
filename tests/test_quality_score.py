from mide.quality_score import (
    QUALITY_WEIGHTS,
    calculate_quality_score,
    enrich_quality_score,
    quality_grade,
)


def strong_record(**changes):
    record = {
        "participation_score": 100,
        "higher_lows": True,
        "near_hod": True,
        "ema65_relation": "above",
        "vwap_relation": "above",
        "vwap_distance_pct": 1.0,
        "supertrend_bullish": True,
        "supertrend_flip": True,
        "timeframe_confirmations": 4,
        "rvol_proxy": 4,
        "volume_acceleration": 1.5,
    }
    record.update(changes)
    return record


def test_quality_score_uses_requested_weights_and_is_bounded():
    assert sum(QUALITY_WEIGHTS.values()) == 100
    result = calculate_quality_score(strong_record())

    assert result["quality_score"] == 100
    assert result["quality_grade"] == "A+"
    assert result["quality_score_breakdown"] == QUALITY_WEIGHTS
    assert 0 <= calculate_quality_score({})["quality_score"] <= 100


def test_quality_grade_boundaries():
    expected = {
        100: "A+",
        95: "A+",
        94: "A",
        90: "A",
        89: "B+",
        85: "B+",
        84: "B",
        80: "B",
        79: "C",
        75: "C",
        74: "Watch Only",
        0: "Watch Only",
    }
    assert {score: quality_grade(score) for score in expected} == expected


def test_quality_is_additive_and_does_not_change_scanner_state():
    candidate = strong_record(status="Strengthening", qualified_for_ranking=True)
    original_state = (candidate["status"], candidate["qualified_for_ranking"])
    assert enrich_quality_score(candidate) is candidate
    assert (candidate["status"], candidate["qualified_for_ranking"]) == original_state


def test_extension_lowers_ranking_without_rejecting_candidate():
    normal = calculate_quality_score(strong_record(vwap_distance_pct=1.0))
    extended = calculate_quality_score(strong_record(vwap_distance_pct=7.0))
    assert extended["quality_score"] < normal["quality_score"]

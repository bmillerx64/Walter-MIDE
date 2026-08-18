import pandas as pd

from mide.timeframe_alignment import (
    alignment_summary,
    alignment_voice,
    evaluate_timeframe,
)
from mide.trader_priority import trader_priority_sort_key


def bars(direction=1, periods=90, start="2026-07-29 13:30:00+00:00", freq="30s"):
    closes = [10 + direction * index * 0.03 for index in range(periods)]
    return pd.DataFrame(
        {
            "open": closes,
            "high": [value + 0.02 for value in closes],
            "low": [value - 0.02 for value in closes],
            "close": closes,
            "volume": [1_000] * periods,
        },
        index=pd.date_range(start, periods=periods, freq=freq),
    )


def test_timeframe_evidence_evaluates_all_requested_indicators():
    result = evaluate_timeframe(bars())
    assert result == {
        "above_vwap": True,
        "supertrend_bullish": True,
        "above_ema65": True,
        "higher_highs_higher_lows": True,
        "aligned": True,
    }


def test_alignment_score_and_labels_cover_three_two_one_and_zero():
    bullish = bars()
    bearish = bars(direction=-1)
    expected = {3: "Strong", 2: "Good", 1: "Weak", 0: "Countertrend"}
    for count, label in expected.items():
        frames = {
            timeframe: bullish if index < count else bearish
            for index, timeframe in enumerate(("30s", "1m", "3m"))
        }
        result = alignment_summary(frames)
        assert result["alignment_score"] == count
        assert result["alignment_label"] == label


def test_alignment_is_ranking_only_and_formats_voice_alert():
    base = {"current_momentum": 50, "historical_strength": 20, "symbol": "GSUN"}
    strong = {**base, "alignment_score": 3}
    weak = {**base, "alignment_score": 1}
    assert trader_priority_sort_key(strong) > trader_priority_sort_key(weak)
    assert "qualified_for_ranking" not in strong
    assert alignment_voice({"alignment_score": 2, "alignment_label": "Good"}) == (
        "Alignment two of three. Good."
    )

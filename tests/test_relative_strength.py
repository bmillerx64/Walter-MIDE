import pandas as pd

from mide.relative_strength import benchmark_for, relative_strength_metrics
from mide.trader_priority import trader_priority_sort_key


def _frame(values):
    return pd.DataFrame({"close": values})


def test_relative_strength_calculates_each_intraday_window_and_score():
    candidate = _frame([100.0] * 11 + [110.0] * 5 + [121.0])
    benchmark = _frame([100.0] * 11 + [105.0] * 5 + [110.0])

    result = relative_strength_metrics(candidate, benchmark)

    assert result["relative_performance_5m_pct"] == 5.24
    assert result["relative_performance_15m_pct"] == 11.0
    assert result["relative_performance_since_open_pct"] == 11.0
    assert result["relative_strength_score"] == 9.08
    assert result["relative_strength_ranking_component"] == 0.726


def test_small_caps_use_iwm_and_larger_candidates_use_spy():
    assert benchmark_for({"float_shares": 3_500_000}) == "IWM"
    assert benchmark_for({"market_cap": 3_000_000_000}) == "SPY"
    assert benchmark_for({}) == "SPY"


def test_rs_is_a_small_ranking_signal_and_never_a_filter():
    weak = {
        "current_momentum": 50,
        "historical_strength": 40,
        "relative_strength_score": -4,
    }
    strong = {
        "current_momentum": 50,
        "historical_strength": 40,
        "relative_strength_score": 4,
    }

    assert trader_priority_sort_key(strong) > trader_priority_sort_key(weak)
    assert strong.get("qualified_for_ranking") is None
    assert trader_priority_sort_key(
        {**weak, "current_momentum": 51}
    ) > trader_priority_sort_key(strong)

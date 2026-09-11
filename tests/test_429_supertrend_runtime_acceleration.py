from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from mide.indicators import atr, supertrend


def _legacy_supertrend_reference(
    df: pd.DataFrame, period: int = 10, multiplier: float = 3.0
):
    """Frozen pre-GS429 implementation used only to prove result identity."""
    if len(df) < period + 2:
        return pd.Series(index=df.index, dtype=float), pd.Series(
            index=df.index, dtype=bool
        )
    hl2 = (df["high"] + df["low"]) / 2
    atr_value = atr(df, period)
    upper = hl2 + multiplier * atr_value
    lower = hl2 - multiplier * atr_value
    final_upper = upper.copy()
    final_lower = lower.copy()
    trend = pd.Series(True, index=df.index, dtype=bool)
    st = pd.Series(np.nan, index=df.index, dtype=float)

    for i in range(1, len(df)):
        prev = i - 1
        if pd.isna(atr_value.iloc[i]):
            continue
        if pd.isna(final_upper.iloc[prev]) or pd.isna(final_lower.iloc[prev]):
            final_upper.iloc[i] = upper.iloc[i]
            final_lower.iloc[i] = lower.iloc[i]
            trend.iloc[i] = trend.iloc[prev]
            st.iloc[i] = final_lower.iloc[i] if trend.iloc[i] else final_upper.iloc[i]
            continue
        if (
            upper.iloc[i] < final_upper.iloc[prev]
            or df["close"].iloc[prev] > final_upper.iloc[prev]
        ):
            final_upper.iloc[i] = upper.iloc[i]
        else:
            final_upper.iloc[i] = final_upper.iloc[prev]
        if (
            lower.iloc[i] > final_lower.iloc[prev]
            or df["close"].iloc[prev] < final_lower.iloc[prev]
        ):
            final_lower.iloc[i] = lower.iloc[i]
        else:
            final_lower.iloc[i] = final_lower.iloc[prev]

        if trend.iloc[prev]:
            trend.iloc[i] = df["close"].iloc[i] >= final_lower.iloc[i]
        else:
            trend.iloc[i] = df["close"].iloc[i] > final_upper.iloc[i]
        st.iloc[i] = final_lower.iloc[i] if trend.iloc[i] else final_upper.iloc[i]
    return st, trend


def _frame(seed: int, rows: int) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    moves = rng.normal(0.0, 0.035, rows)
    close = np.maximum(0.05, 2.0 + np.cumsum(moves))
    spread_high = np.abs(rng.normal(0.018, 0.009, rows))
    spread_low = np.abs(rng.normal(0.018, 0.009, rows))
    high = close + spread_high
    low = np.maximum(0.001, close - spread_low)
    opening = np.concatenate(([close[0]], close[:-1]))
    volume = rng.integers(1_000, 4_000_000, rows).astype(float)
    index = pd.date_range("2026-09-10 04:00", periods=rows, freq="min", tz="America/New_York")
    return pd.DataFrame(
        {"open": opening, "high": high, "low": low, "close": close, "volume": volume},
        index=index,
    )


@pytest.mark.parametrize("rows", [12, 35, 150, 390, 960])
@pytest.mark.parametrize("seed", [1, 7, 29])
@pytest.mark.parametrize("period,multiplier", [(7, 2.0), (10, 3.0), (14, 4.0)])
def test_gs429_matches_frozen_supertrend_exactly(rows, seed, period, multiplier):
    frame = _frame(seed, rows)
    expected_line, expected_trend = _legacy_supertrend_reference(
        frame, period, multiplier
    )
    actual_line, actual_trend = supertrend(frame, period, multiplier)

    np.testing.assert_array_equal(
        actual_line.to_numpy(), expected_line.to_numpy()
    )
    pd.testing.assert_index_equal(actual_line.index, expected_line.index)
    pd.testing.assert_series_equal(actual_trend, expected_trend, check_names=True)


def test_gs429_matches_flat_tape_and_reversal_edges_exactly():
    rows = 240
    index = pd.date_range("2026-09-10 09:30", periods=rows, freq="min", tz="America/New_York")
    close = np.concatenate(
        [
            np.full(40, 1.0),
            np.linspace(1.0, 2.4, 70),
            np.linspace(2.4, 0.55, 80),
            np.linspace(0.55, 1.35, 50),
        ]
    )
    frame = pd.DataFrame(
        {
            "open": np.concatenate(([close[0]], close[:-1])),
            "high": close + 0.02,
            "low": np.maximum(0.001, close - 0.02),
            "close": close,
            "volume": np.linspace(10_000, 900_000, rows),
        },
        index=index,
    )

    expected_line, expected_trend = _legacy_supertrend_reference(frame)
    actual_line, actual_trend = supertrend(frame)
    np.testing.assert_array_equal(actual_line.to_numpy(), expected_line.to_numpy())
    pd.testing.assert_series_equal(actual_trend, expected_trend)


def test_gs429_preserves_short_history_contract():
    frame = _frame(3, 11)
    line, trend = supertrend(frame, period=10, multiplier=3.0)
    assert line.index.equals(frame.index)
    assert trend.index.equals(frame.index)
    assert len(line) == len(frame)
    assert len(trend) == len(frame)
    assert line.isna().all()
    assert trend.dtype == bool

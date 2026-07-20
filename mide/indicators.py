from __future__ import annotations
import numpy as np
import pandas as pd

def ema(series: pd.Series, period: int) -> pd.Series:
    return series.astype(float).ewm(span=period, adjust=False, min_periods=period).mean()

def session_vwap(df: pd.DataFrame) -> pd.Series:
    typical = (df["high"] + df["low"] + df["close"]) / 3.0
    vol = df["volume"].replace(0, np.nan)
    return (typical * vol).cumsum() / vol.cumsum()

def atr(df: pd.DataFrame, period: int = 10) -> pd.Series:
    previous = df["close"].shift(1)
    tr = pd.concat([
        df["high"] - df["low"],
        (df["high"] - previous).abs(),
        (df["low"] - previous).abs(),
    ], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()

def supertrend(df: pd.DataFrame, period: int = 10, multiplier: float = 3.0):
    if len(df) < period + 2:
        return pd.Series(index=df.index, dtype=float), pd.Series(index=df.index, dtype=bool)
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
        if upper.iloc[i] < final_upper.iloc[prev] or df["close"].iloc[prev] > final_upper.iloc[prev]:
            final_upper.iloc[i] = upper.iloc[i]
        else:
            final_upper.iloc[i] = final_upper.iloc[prev]
        if lower.iloc[i] > final_lower.iloc[prev] or df["close"].iloc[prev] < final_lower.iloc[prev]:
            final_lower.iloc[i] = lower.iloc[i]
        else:
            final_lower.iloc[i] = final_lower.iloc[prev]

        if trend.iloc[prev]:
            trend.iloc[i] = df["close"].iloc[i] >= final_lower.iloc[i]
        else:
            trend.iloc[i] = df["close"].iloc[i] > final_upper.iloc[i]
        st.iloc[i] = final_lower.iloc[i] if trend.iloc[i] else final_upper.iloc[i]
    return st, trend

def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.astype(float).diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))

def resample_ohlcv(df: pd.DataFrame, rule: str) -> pd.DataFrame:
    x = df.copy()
    if not isinstance(x.index, pd.DatetimeIndex):
        x.index = pd.to_datetime(x.index, utc=True)
    return x.resample(rule).agg({
        "open": "first", "high": "max", "low": "min",
        "close": "last", "volume": "sum"
    }).dropna()

def volume_acceleration(df: pd.DataFrame, recent_bars: int = 3, baseline_bars: int = 12) -> float:
    if len(df) < recent_bars + baseline_bars:
        return 1.0
    recent = df["volume"].tail(recent_bars).mean()
    baseline = df["volume"].iloc[-(recent_bars + baseline_bars):-recent_bars].mean()
    return float(recent / baseline) if baseline and baseline > 0 else 1.0

def green_volume_ratio(df: pd.DataFrame, bars: int = 12) -> float:
    x = df.tail(bars)
    green = x.loc[x["close"] >= x["open"], "volume"].sum()
    red = x.loc[x["close"] < x["open"], "volume"].sum()
    if red <= 0:
        return 3.0 if green > 0 else 1.0
    return float(green / red)

def higher_lows(df: pd.DataFrame, bars: int = 6) -> bool:
    lows = df["low"].tail(bars)
    if len(lows) < 4:
        return False
    return bool(lows.iloc[-1] > lows.iloc[-3] and lows.iloc[-2] > lows.iloc[-4])

def proximity_pct(price: float, level: float) -> float:
    if not level or np.isnan(level):
        return 999.0
    return abs(price - level) / level * 100.0

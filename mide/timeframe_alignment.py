"""Multi-timeframe trend context used only to rank and explain candidates."""

from __future__ import annotations

import math

import pandas as pd

from .indicators import ema, higher_lows, session_vwap, supertrend

# 30s / 1m / 3m aligns with the user's target confirmation ladder.
# 5m was previously used but lags too much for early small-cap detection;
# 3m provides an earlier and more relevant intermediate confirmation.
TIMEFRAMES = ("30s", "1m", "3m")
ALIGNMENT_LABELS = {3: "Strong", 2: "Good", 1: "Weak", 0: "Countertrend"}


def _higher_highs(frame: pd.DataFrame, bars: int = 6) -> bool | None:
    highs = frame["high"].tail(bars)
    if len(highs) < 4:
        return None
    return bool(highs.iloc[-1] > highs.iloc[-3] and highs.iloc[-2] > highs.iloc[-4])


def evaluate_timeframe(frame: pd.DataFrame) -> dict:
    """Return the latest bullish trend evidence for one OHLCV timeframe."""
    if frame is None or frame.empty:
        return {
            "above_vwap": False,
            "supertrend_bullish": False,
            "above_ema65": False,
            "higher_highs_higher_lows": None,
            "aligned": False,
        }
    close = float(frame["close"].iloc[-1])
    vwap = session_vwap(frame).iloc[-1]
    ema65 = ema(frame["close"], 65).iloc[-1] if len(frame) >= 65 else float("nan")
    _, direction = supertrend(frame, 10, 3)
    hh = _higher_highs(frame)
    hl = higher_lows(frame) if len(frame) >= 4 else None
    structure = None if hh is None or hl is None else bool(hh and hl)
    above_vwap = bool(not pd.isna(vwap) and close >= float(vwap))
    st_bullish = bool(len(direction) and direction.iloc[-1])
    above_ema = bool(not math.isnan(float(ema65)) and close >= float(ema65))
    # Structure is supporting evidence when enough bars exist, not a new gate.
    aligned = above_vwap and st_bullish and above_ema and structure is not False
    return {
        "above_vwap": above_vwap,
        "supertrend_bullish": st_bullish,
        "above_ema65": above_ema,
        "higher_highs_higher_lows": structure,
        "aligned": aligned,
    }


def alignment_summary(frames: dict[str, pd.DataFrame]) -> dict:
    details = {label: evaluate_timeframe(frames.get(label)) for label in TIMEFRAMES}
    score = sum(bool(item["aligned"]) for item in details.values())
    return {
        "alignment_score": score,
        "alignment_total": len(TIMEFRAMES),
        "alignment_label": ALIGNMENT_LABELS[score],
        "timeframe_alignment": details,
    }


def alignment_voice(record: dict) -> str:
    """Format the short audible alignment suffix for a candidate."""
    if record.get("alignment_score") is None:
        return ""
    score = max(0, min(3, int(record["alignment_score"])))
    label = str(record.get("alignment_label") or ALIGNMENT_LABELS[score])
    words = ("zero", "one", "two", "three")
    return f"Alignment {words[score]} of three. {label}."

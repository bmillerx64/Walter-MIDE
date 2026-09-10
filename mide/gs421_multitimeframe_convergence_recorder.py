"""GS421: record multi-timeframe momentum convergence without changing authority.

Live TNON validation on 2026-09-10 showed a useful progression that Walter already
partly observes but does not yet preserve as one coherent sequence:

    30s tripwire -> 1m ignition -> 3m confirmation -> 5m/10m/15m maturation

The important lesson is not that a slower SuperTrend flip should create a new entry.
It is that a move may become more credible as momentum, VWAP agreement, participation,
and progressively slower chart timeframes converge. GS421 records that maturation so
future live evidence can tell us which convergence profiles repeatedly produce strong
follow-through.

This module is observational only. It reuses the exact 1-minute history already
captured by GS378 and performs local resampling. It does not request market data and
does not change discovery, ranking, scoring, qualification, readiness, VWAP/chase
rules, alerts/audio, execution, orders, or the 30s/1m/3m authority contract.
"""
from __future__ import annotations

from functools import wraps
from typing import Any

import pandas as pd

from . import gs378_live_vwap_st_crossover as gs378
from .indicators import resample_ohlcv, supertrend

AUTHORITY = "OBSERVATIONAL_ONLY"
SOURCE = "GS378 already-fetched current-session Webull 1Min bars"
TIMEFRAME_RULES = {
    "1m": None,
    "3m": "3min",
    "5m": "5min",
    "10m": "10min",
    "15m": "15min",
}
MATURATION_ORDER = tuple(TIMEFRAME_RULES)


def _number(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if pd.isna(number):
        return None
    return number


def _timeframe_frame(day: pd.DataFrame, label: str) -> pd.DataFrame:
    rule = TIMEFRAME_RULES[label]
    return day if rule is None else resample_ohlcv(day, rule)


def _timeframe_vwap(primary_1m: pd.Series, label: str) -> pd.Series:
    rule = TIMEFRAME_RULES[label]
    if rule is None:
        return primary_1m
    return primary_1m.resample(rule).last().dropna()


def _timeframe_event(
    day: pd.DataFrame,
    primary_1m: pd.Series,
    label: str,
) -> dict:
    """Describe current state and latest bullish ST flip while price was above VWAP."""
    tf = _timeframe_frame(day, label)
    vwap = _timeframe_vwap(primary_1m, label).reindex(tf.index)
    if len(tf) < 2 or vwap.empty:
        return {
            "timeframe": label,
            "data_available": False,
            "current_supertrend_bullish": False,
            "current_above_vwap": False,
            "current_confirmed": False,
            "bullish_flip_timestamp": None,
            "bullish_flip_age_seconds": None,
        }

    st_line, trend = supertrend(tf, 10, 3)
    bullish = trend.fillna(False).astype(bool)
    prior_bullish = bullish.shift(1).fillna(False).astype(bool)
    close = tf["close"].astype(float)
    valid = st_line.notna() & vwap.notna()
    flip_mask = valid & bullish & (~prior_bullish) & (close >= vwap)
    hits = list(flip_mask[flip_mask].index)
    flip_time = hits[-1] if hits else None

    latest_vwap = _number(vwap.iloc[-1]) if len(vwap) else None
    latest_close = _number(close.iloc[-1])
    current_bullish = bool(len(bullish) and bullish.iloc[-1])
    current_above_vwap = bool(
        latest_close is not None and latest_vwap is not None and latest_close >= latest_vwap
    )

    event = {
        "timeframe": label,
        "data_available": bool(valid.any()),
        "current_supertrend_bullish": current_bullish,
        "current_above_vwap": current_above_vwap,
        "current_confirmed": bool(current_bullish and current_above_vwap),
        "current_close": latest_close,
        "current_vwap": latest_vwap,
        "bullish_flip_timestamp": flip_time.isoformat() if flip_time is not None else None,
        "bullish_flip_age_seconds": None,
    }
    if flip_time is not None:
        age = max(0.0, (day.index[-1] - flip_time).total_seconds())
        flip_price = _number(close.loc[flip_time])
        flip_vwap = _number(vwap.loc[flip_time])
        event.update(
            {
                "bullish_flip_age_seconds": round(age, 1),
                "price_at_flip": flip_price,
                "vwap_at_flip": flip_vwap,
                "vwap_distance_at_flip_pct": (
                    round((flip_price - flip_vwap) / flip_vwap * 100.0, 4)
                    if flip_price is not None and flip_vwap not in (None, 0)
                    else None
                ),
                "supertrend_at_flip": _number(st_line.loc[flip_time]),
                "volume_at_flip": _number(tf.loc[flip_time, "volume"]),
            }
        )
    return event


def _timestamp(value: Any) -> pd.Timestamp | None:
    if not value:
        return None
    try:
        stamp = pd.Timestamp(value)
    except Exception:
        return None
    if stamp.tzinfo is None:
        stamp = stamp.tz_localize(gs378.EASTERN)
    return stamp


def _cascade(events: dict[str, dict]) -> list[str]:
    """Return the consecutive 1m->15m bullish-flip sequence observed so far."""
    observed: list[str] = []
    prior: pd.Timestamp | None = None
    for label in MATURATION_ORDER:
        stamp = _timestamp((events.get(label) or {}).get("bullish_flip_timestamp"))
        if stamp is None:
            break
        if prior is not None and stamp < prior:
            break
        observed.append(label)
        prior = stamp
    return observed


def _delays_from_1m(events: dict[str, dict]) -> dict[str, float | None]:
    one = _timestamp((events.get("1m") or {}).get("bullish_flip_timestamp"))
    result: dict[str, float | None] = {}
    for label in ("3m", "5m", "10m", "15m"):
        later = _timestamp((events.get(label) or {}).get("bullish_flip_timestamp"))
        result[label] = (
            round((later - one).total_seconds(), 1)
            if one is not None and later is not None and later >= one
            else None
        )
    return result


def _excursion_since_1m(day: pd.DataFrame, one_minute: dict) -> dict:
    stamp = _timestamp(one_minute.get("bullish_flip_timestamp"))
    entry = _number(one_minute.get("price_at_flip"))
    if stamp is None or entry in (None, 0):
        return {
            "reference_price": entry,
            "max_favorable_excursion_pct": None,
            "max_adverse_excursion_pct": None,
        }
    after = day[day.index >= stamp]
    if after.empty:
        return {
            "reference_price": entry,
            "max_favorable_excursion_pct": None,
            "max_adverse_excursion_pct": None,
        }
    high = _number(after["high"].max())
    low = _number(after["low"].min())
    return {
        "reference_price": entry,
        "max_favorable_excursion_pct": (
            round((high - entry) / entry * 100.0, 4) if high is not None else None
        ),
        "max_adverse_excursion_pct": (
            round((low - entry) / entry * 100.0, 4) if low is not None else None
        ),
    }


def _pre_ignition_context(
    day: pd.DataFrame,
    primary_1m: pd.Series,
    one_minute: dict,
) -> dict:
    stamp = _timestamp(one_minute.get("bullish_flip_timestamp"))
    if stamp is None:
        return {}
    output: dict[str, dict] = {}
    for minutes in (30, 60, 120, 240):
        start = stamp - pd.Timedelta(minutes=minutes)
        window = day[(day.index >= start) & (day.index < stamp)]
        common = window.index.intersection(primary_1m.index)
        if len(common) < 2:
            continue
        window = window.loc[common]
        vwaps = primary_1m.loc[common].astype(float)
        closes = window["close"].astype(float)
        reference = _number(closes.iloc[-1])
        high = _number(window["high"].max())
        low = _number(window["low"].min())
        distances = ((closes - vwaps) / vwaps * 100.0).abs()
        output[f"{minutes}m"] = {
            "bars": int(len(window)),
            "range_pct": (
                round((high - low) / reference * 100.0, 4)
                if high is not None and low is not None and reference not in (None, 0)
                else None
            ),
            "median_abs_vwap_distance_pct": (
                round(float(distances.median()), 4) if len(distances) else None
            ),
            "total_volume": _number(window["volume"].sum()),
        }
    return output


def build_maturation_evidence(record: dict, raw_rows, client) -> dict:
    """Build detached TNON-style convergence evidence from already-captured history."""
    frame = client.bars_frame(raw_rows or [])
    context = gs378.primary_vwap_context(frame)
    day = context.get("day")
    primary = context.get("series")
    if day is None or day.empty or primary is None or primary.empty:
        return {
            "authority": AUTHORITY,
            "source": SOURCE,
            "available": False,
            "timeframes": {},
        }

    events = {
        label: _timeframe_event(day, primary, label)
        for label in MATURATION_ORDER
    }
    cascade = _cascade(events)
    current_confirmed = [
        label for label in MATURATION_ORDER if events[label].get("current_confirmed")
    ]

    return {
        "authority": AUTHORITY,
        "source": SOURCE,
        "available": True,
        "model": "30s tripwire -> 1m ignition -> 3m confirmation -> 5m/10m/15m maturation",
        "entry_authority_changed": False,
        "thirty_second": {
            "investigation_tripwire": bool(record.get("operator_investigation_tripwire")),
            "supertrend_bullish": bool(record.get("supertrend_30s_bullish")),
            "last_flip_timestamp": record.get("supertrend_30s_last_flip_timestamp"),
            "last_flip_age_seconds": _number(record.get("supertrend_30s_last_flip_age_seconds")),
        },
        "timeframes": events,
        "observed_cascade": cascade,
        "cascade_depth": len(cascade),
        "highest_observed_maturation": cascade[-1] if cascade else None,
        "current_confirmed_timeframes": current_confirmed,
        "current_convergence_count": len(current_confirmed),
        "seconds_from_1m_ignition": _delays_from_1m(events),
        "excursion_since_1m_ignition": _excursion_since_1m(day, events["1m"]),
        "pre_ignition_context": _pre_ignition_context(day, primary, events["1m"]),
        "scan_snapshot": {
            "price": _number(record.get("price")),
            "vwap_distance_pct": _number(record.get("vwap_distance_pct")),
            "participation_score": _number(record.get("participation_score")),
            "participation_surge_score": _number(record.get("participation_surge_score")),
            "expansion_score": _number(record.get("expansion_score")),
            "volume_acceleration": _number(record.get("volume_acceleration")),
            "dollar_flow_acceleration": _number(record.get("dollar_flow_acceleration")),
            "qualified_for_watch": bool(record.get("qualified_for_watch")),
            "qualified_for_entry": bool(record.get("qualified_for_entry")),
            "status": record.get("status"),
        },
    }


def _inherit(wrapper, wrapped) -> None:
    for name, value in getattr(wrapped, "__dict__", {}).items():
        if name.startswith("_gs") and not hasattr(wrapper, name):
            setattr(wrapper, name, value)


def install() -> None:
    """Attach convergence evidence after GS397 using GS378's captured history only."""
    current = gs378.apply_live_vwap_truth
    if getattr(current, "_gs421_multitimeframe_convergence", False):
        return

    @wraps(current)
    def apply_with_maturation(records, current_session_raw, current_session_30s_raw, client):
        updated = current(records, current_session_raw, current_session_30s_raw, client)
        annotated = 0
        for record in updated or []:
            symbol = str(record.get("symbol") or "").strip().upper()
            if not symbol:
                continue
            evidence = build_maturation_evidence(
                record,
                (current_session_raw or {}).get(symbol) or [],
                client,
            )
            record["multitimeframe_maturation"] = evidence
            record["multitimeframe_maturation_authority"] = AUTHORITY
            if evidence.get("available"):
                annotated += 1

        diagnostics = getattr(client, "diagnostics", None)
        if isinstance(diagnostics, dict):
            diagnostics["gs421_multitimeframe_convergence"] = {
                "authority": AUTHORITY,
                "source": SOURCE,
                "timeframes": list(MATURATION_ORDER),
                "records_annotated": annotated,
                "additional_history_requests": 0,
                "entry_authority_changed": False,
                "ranking_changed": False,
                "scoring_changed": False,
                "qualification_changed": False,
            }
        return updated

    _inherit(apply_with_maturation, current)
    apply_with_maturation._gs421_multitimeframe_convergence = True
    apply_with_maturation._gs421_original = current
    gs378.apply_live_vwap_truth = apply_with_maturation

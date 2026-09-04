"""GS378: make live VWAP and SuperTrend/VWAP crossover evidence time-correct.

Why this exists
---------------
Walter has always requested current-session history from 04:00 ET so premarket
structure is available.  That history-start boundary accidentally became the
primary VWAP anchor because ``discovery.analyze_candidates`` fed the entire
04:00+ frame into ``session_vwap``.  Once regular trading begins, that can make a
mid-morning setup answer to hours of premarket volume instead of the regular-session
VWAP a trader sees and acts on.

GS378 separates those concepts:
* 04:00 ET remains the history acquisition / premarket context boundary.
* Before 09:30 ET, Walter uses the available premarket VWAP.
* At and after 09:30 ET, Walter's *primary* VWAP resets at 09:30 ET.
* Premarket VWAP remains available as secondary context; it is not discarded.
* SuperTrend remains seeded from the available current-day bars.  Resetting a
  10-period SuperTrend at 09:30 would make a genuine 09:31/09:32 flip impossible
  to detect, so premarket history may seed the line without controlling VWAP.

Crossover truth is reconstructed from the 1-minute history Walter already fetched
for Stage 6.  It is not inferred from one scan's last values versus the next scan's
last values.  That makes 1m and 3m ST/VWAP crosses deterministic across Streamlit
reruns and prevents a 60-second scan cadence from silently skipping an intrabar
transition.

No additional market-data request is made.  GS378 temporarily observes the exact
``stage6_current_session`` history call that ``analyze_candidates`` already makes,
then corrects VWAP-derived evidence and rescoring before the records leave Stage 6.
Existing thresholds, entry rules, execution, and order logic are not widened.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import fields
from functools import wraps
import math
from typing import Any

import pandas as pd

from .indicators import ema, higher_lows, resample_ohlcv, session_vwap, supertrend
from .scoring import Evidence, score

EASTERN = "America/New_York"
RTH_OPEN_HOUR = 9
RTH_OPEN_MINUTE = 30
PREMARKET_OPEN_HOUR = 4

# A crossover remains visible long enough for an operator to inspect it, but only
# the very recent edge is treated as a new audible/event transition by GS348.
CROSS_RECENT_SECONDS = {"1m": 10 * 60, "3m": 15 * 60}
CROSS_NEW_SECONDS = {"1m": 90, "3m": 150}

_ALIGNMENT_LABELS = {3: "Strong", 2: "Good", 1: "Weak", 0: "Countertrend"}
_TIMEFRAME_RULES = {
    "1m": None,
    "3m": "3min",
    "5m": "5min",
    "10m": "10min",
}


def _finite_number(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _eastern_day(frame: pd.DataFrame | None) -> pd.DataFrame:
    """Return only the latest U.S. trading date with an Eastern-aware index."""
    if frame is None or frame.empty:
        return pd.DataFrame()
    x = frame.copy()
    if not isinstance(x.index, pd.DatetimeIndex):
        x.index = pd.to_datetime(x.index, utc=True, errors="coerce")
    elif x.index.tz is None:
        # Provider bars are normalized to UTC.  Tests/legacy callers with a naive
        # index therefore receive the same interpretation rather than machine local time.
        x.index = x.index.tz_localize("UTC")
    x = x[~x.index.isna()].sort_index()
    if x.empty:
        return x
    x.index = x.index.tz_convert(EASTERN)
    latest_date = x.index[-1].date()
    return x[x.index.date == latest_date].copy()


def _session_boundaries(day: pd.DataFrame) -> tuple[pd.Timestamp, pd.Timestamp]:
    midnight = day.index[-1].normalize()
    premarket = midnight + pd.Timedelta(hours=PREMARKET_OPEN_HOUR)
    regular = midnight + pd.Timedelta(hours=RTH_OPEN_HOUR, minutes=RTH_OPEN_MINUTE)
    return premarket, regular


def primary_vwap_context(frame: pd.DataFrame | None) -> dict:
    """Return Walter's current primary VWAP plus explicit anchor diagnostics.

    04:00 ET is used only while the latest bar is premarket.  Once a 09:30 ET or
    later bar exists, primary VWAP is rebuilt from 09:30 ET forward.
    """
    day = _eastern_day(frame)
    if day.empty:
        return {
            "day": day,
            "series": pd.Series(dtype=float),
            "value": None,
            "anchor_mode": "UNAVAILABLE",
            "anchor_time": None,
            "premarket_value": None,
        }

    premarket_start, regular_start = _session_boundaries(day)
    latest = day.index[-1]
    if latest >= regular_start:
        anchor = regular_start
        mode = "RTH_09:30_ET"
    else:
        anchor = premarket_start
        mode = "PREMARKET_04:00_ET"

    anchored = day[day.index >= anchor].copy()
    if anchored.empty:
        # Fail visibly rather than manufacturing a 09:30 VWAP from earlier bars.
        anchored = day.copy()
        anchor = day.index[0]
        mode = "FALLBACK_FIRST_AVAILABLE_BAR"

    vwaps = session_vwap(anchored)
    value = _finite_number(vwaps.iloc[-1]) if len(vwaps) else None

    premarket = day[(day.index >= premarket_start) & (day.index < regular_start)]
    premarket_value = None
    if not premarket.empty:
        premarket_series = session_vwap(premarket)
        if len(premarket_series):
            premarket_value = _finite_number(premarket_series.iloc[-1])

    return {
        "day": day,
        "series": vwaps,
        "value": value,
        "anchor_mode": mode,
        "anchor_time": anchor,
        "premarket_value": premarket_value,
    }


def _timeframe_frame(day: pd.DataFrame, label: str) -> pd.DataFrame:
    rule = _TIMEFRAME_RULES.get(label)
    return day if rule is None else resample_ohlcv(day, rule)


def _timeframe_vwap(primary_series: pd.Series, label: str) -> pd.Series:
    """Project one primary 1m VWAP truth onto a chart timeframe.

    VWAP is cumulative session evidence and should not acquire a different anchor
    merely because the operator switches from a 1m to a 3m chart.  For resampled
    bars, use the last primary VWAP observed inside that bar.
    """
    if primary_series.empty:
        return primary_series
    rule = _TIMEFRAME_RULES.get(label)
    if rule is None:
        return primary_series
    return primary_series.resample(rule).last().dropna()


def _latest_event(mask: pd.Series) -> pd.Timestamp | None:
    hits = list(mask[mask.fillna(False)].index)
    return hits[-1] if hits else None


def st_vwap_timeframe_event(
    frame: pd.DataFrame | None,
    label: str,
    *,
    primary_context: dict | None = None,
) -> dict:
    """Detect the latest bullish ST-line cross above the primary VWAP on one timeframe."""
    context = primary_context or primary_vwap_context(frame)
    day = context.get("day")
    if day is None or day.empty or label not in {"1m", "3m"}:
        return {
            "timeframe": label,
            "crossed": False,
            "recent": False,
            "new": False,
            "timestamp": None,
            "age_seconds": None,
            "age_bars": None,
            "bullish_flip_timestamp": None,
            "bullish_flip_age_seconds": None,
        }

    tf = _timeframe_frame(day, label)
    primary = _timeframe_vwap(context["series"], label)
    if len(tf) < 2 or primary.empty:
        return {
            "timeframe": label,
            "crossed": False,
            "recent": False,
            "new": False,
            "timestamp": None,
            "age_seconds": None,
            "age_bars": None,
            "bullish_flip_timestamp": None,
            "bullish_flip_age_seconds": None,
        }

    st_line, trend = supertrend(tf, 10, 3)
    vwap = primary.reindex(tf.index)
    valid = st_line.notna() & vwap.notna()
    line_delta = st_line - vwap
    close = tf["close"].astype(float)

    cross_mask = (
        valid
        & (line_delta.shift(1) < 0)
        & (line_delta >= 0)
        & trend.fillna(False).astype(bool)
        & (close >= vwap)
    )
    cross_time = _latest_event(cross_mask)

    prior_trend = trend.shift(1).fillna(False).astype(bool)
    flip_mask = (
        valid
        & trend.fillna(False).astype(bool)
        & (~prior_trend)
        & (close >= vwap)
    )
    flip_time = _latest_event(flip_mask)

    latest_source_time = day.index[-1]
    age_seconds = (
        max(0.0, (latest_source_time - cross_time).total_seconds())
        if cross_time is not None
        else None
    )
    flip_age_seconds = (
        max(0.0, (latest_source_time - flip_time).total_seconds())
        if flip_time is not None
        else None
    )
    age_bars = None
    if cross_time is not None:
        try:
            age_bars = max(0, len(tf) - 1 - int(tf.index.get_loc(cross_time)))
        except Exception:
            age_bars = None

    recent_window = CROSS_RECENT_SECONDS[label]
    new_window = CROSS_NEW_SECONDS[label]
    recent = bool(age_seconds is not None and age_seconds <= recent_window)
    new = bool(age_seconds is not None and age_seconds <= new_window)

    event = {
        "timeframe": label,
        "crossed": cross_time is not None,
        "recent": recent,
        "new": new,
        "timestamp": cross_time.isoformat() if cross_time is not None else None,
        "age_seconds": round(age_seconds, 1) if age_seconds is not None else None,
        "age_bars": age_bars,
        "bullish_flip_timestamp": flip_time.isoformat() if flip_time is not None else None,
        "bullish_flip_age_seconds": (
            round(flip_age_seconds, 1) if flip_age_seconds is not None else None
        ),
    }
    if cross_time is not None:
        event.update(
            {
                "supertrend_value": round(float(st_line.loc[cross_time]), 6),
                "vwap_value": round(float(vwap.loc[cross_time]), 6),
                "price": round(float(close.loc[cross_time]), 6),
                "volume": round(float(tf.loc[cross_time, "volume"]), 2),
            }
        )
    return event


def st_vwap_crossover_evidence(frame: pd.DataFrame | None) -> dict:
    """Return deterministic 1m/3m crossover truth from one already-fetched bar history."""
    context = primary_vwap_context(frame)
    events = {
        label: st_vwap_timeframe_event(frame, label, primary_context=context)
        for label in ("1m", "3m")
    }
    recent = [label for label, event in events.items() if event.get("recent")]
    new = [label for label, event in events.items() if event.get("new")]
    ages = [
        float(event["age_seconds"])
        for event in events.values()
        if event.get("recent") and event.get("age_seconds") is not None
    ]
    signatures = [
        f"{label}@{event['timestamp']}"
        for label, event in events.items()
        if event.get("recent") and event.get("timestamp")
    ]

    flip_1m_age = events["1m"].get("bullish_flip_age_seconds")
    return {
        "st_vwap_cross_recent": bool(recent),
        "st_vwap_cross_new": bool(new),
        "st_vwap_cross_timeframes": recent,
        "st_vwap_cross_new_timeframes": new,
        "st_vwap_cross_multi_timeframe": len(recent) >= 2,
        "st_vwap_cross_age_seconds": round(min(ages), 1) if ages else None,
        "st_vwap_cross_signature": "|".join(signatures) if signatures else None,
        "st_vwap_cross_events": events,
        # Correct the older ambiguous field: this now means an actual ST-line/VWAP
        # transition was reconstructed from bars, not merely "price reclaimed VWAP + ST bullish".
        "crossed_vwap_and_supertrend": bool(recent),
        "supertrend_flipped_last_10m": bool(
            flip_1m_age is not None and float(flip_1m_age) <= 10 * 60
        ),
        "supertrend_flip_age_seconds": (
            round(float(flip_1m_age), 1) if flip_1m_age is not None else None
        ),
    }


def _reclaim_metrics(day: pd.DataFrame, primary_series: pd.Series) -> tuple[bool, int]:
    if day.empty or primary_series.empty:
        return False, 999
    common = day.index.intersection(primary_series.index)
    if len(common) < 2:
        return False, 999
    closes = day.loc[common, "close"].astype(float).tail(11)
    vwaps = primary_series.loc[closes.index].astype(float)
    above = closes >= vwaps
    reclaimed = bool((~above.iloc[:-1]).any() and above.iloc[-1]) if len(above) > 1 else False
    crosses = above & (~above.shift(1).fillna(above.iloc[0]))
    hit_positions = [i for i, value in enumerate(crosses.tolist()) if bool(value)]
    age = len(crosses) - 1 - hit_positions[-1] if hit_positions else 999
    return reclaimed, int(age)


def _confirmation_details(day: pd.DataFrame, primary_series: pd.Series) -> tuple[int, dict]:
    confirmations = 0
    details: dict[str, dict] = {}
    for label in ("1m", "3m", "5m", "10m"):
        tf = _timeframe_frame(day, label)
        if len(tf) < 20:
            continue
        vwap = _timeframe_vwap(primary_series, label).reindex(tf.index)
        st_line, trend = supertrend(tf, 10, 3)
        latest_vwap = _finite_number(vwap.iloc[-1]) if len(vwap) else None
        close = float(tf["close"].iloc[-1])
        bullish = bool(len(trend) and trend.iloc[-1])
        above_vwap = bool(latest_vwap is not None and close >= latest_vwap)
        if bullish and above_vwap:
            confirmations += 1
        details[label] = {"above_vwap": above_vwap, "supertrend": bullish}
    return confirmations, details


def _higher_highs(frame: pd.DataFrame, bars: int = 6) -> bool | None:
    highs = frame["high"].tail(bars)
    if len(highs) < 4:
        return None
    return bool(highs.iloc[-1] > highs.iloc[-3] and highs.iloc[-2] > highs.iloc[-4])


def _alignment_evaluation(frame: pd.DataFrame, primary_series: pd.Series, label: str) -> dict:
    if frame is None or frame.empty:
        return {
            "above_vwap": False,
            "supertrend_bullish": False,
            "above_ema65": False,
            "higher_highs_higher_lows": None,
            "aligned": False,
        }
    tf_vwap = _timeframe_vwap(primary_series, label).reindex(frame.index)
    close = float(frame["close"].iloc[-1])
    latest_vwap = _finite_number(tf_vwap.iloc[-1]) if len(tf_vwap) else None
    ema65 = ema(frame["close"], 65).iloc[-1] if len(frame) >= 65 else float("nan")
    _, direction = supertrend(frame, 10, 3)
    hh = _higher_highs(frame)
    hl = higher_lows(frame) if len(frame) >= 4 else None
    structure = None if hh is None or hl is None else bool(hh and hl)
    above_vwap = bool(latest_vwap is not None and close >= latest_vwap)
    bullish = bool(len(direction) and direction.iloc[-1])
    above_ema = bool(not math.isnan(float(ema65)) and close >= float(ema65))
    aligned = above_vwap and bullish and above_ema and structure is not False
    return {
        "above_vwap": above_vwap,
        "supertrend_bullish": bullish,
        "above_ema65": above_ema,
        "higher_highs_higher_lows": structure,
        "aligned": aligned,
    }


def _alignment_summary(
    day_1m: pd.DataFrame,
    primary_1m: pd.Series,
    frame_30s: pd.DataFrame | None = None,
) -> dict:
    details: dict[str, dict] = {}

    thirty = _eastern_day(frame_30s)
    if not thirty.empty:
        thirty_context = primary_vwap_context(thirty)
        details["30s"] = _alignment_evaluation(
            thirty_context["day"], thirty_context["series"], "1m"
        )
    else:
        details["30s"] = _alignment_evaluation(pd.DataFrame(), pd.Series(dtype=float), "1m")

    details["1m"] = _alignment_evaluation(day_1m, primary_1m, "1m")
    frame_3m = _timeframe_frame(day_1m, "3m")
    details["3m"] = _alignment_evaluation(frame_3m, primary_1m, "3m")
    alignment_score = sum(bool(details[label]["aligned"]) for label in ("30s", "1m", "3m"))
    return {
        "timeframe_alignment": details,
        "alignment_score": alignment_score,
        "alignment_total": 3,
        "alignment_label": _ALIGNMENT_LABELS[alignment_score],
    }


def _rescore_record(record: dict) -> None:
    values = {}
    for field in fields(Evidence):
        if field.name not in record:
            return
        values[field.name] = record[field.name]
    decision = score(Evidence(**values))
    record.update(decision.__dict__)


def apply_live_vwap_truth(
    records: list[dict],
    current_session_raw: dict[str, list[dict]],
    current_session_30s_raw: dict[str, list[dict]] | None,
    client,
) -> list[dict]:
    """Correct Stage-6 records in place using only history already fetched by Stage 6."""
    updated = list(records or [])
    current_session_30s_raw = current_session_30s_raw or {}
    corrected = 0

    for record in updated:
        symbol = str(record.get("symbol") or "").strip().upper()
        if not symbol:
            continue
        raw_rows = current_session_raw.get(symbol) or []
        frame = client.bars_frame(raw_rows)
        context = primary_vwap_context(frame)
        day = context["day"]
        primary_series = context["series"]
        primary_value = context["value"]
        if day.empty or primary_value is None:
            continue

        price = _finite_number(record.get("price"))
        distance = (
            ((price - primary_value) / primary_value * 100.0)
            if price is not None and primary_value
            else None
        )
        if distance is None:
            continue
        relation = "above" if distance >= 0 else ("testing" if distance >= -1.0 else "below")
        reclaimed, reclaim_age = _reclaim_metrics(day, primary_series)
        confirmations, confirmation_details = _confirmation_details(day, primary_series)

        record.update(
            {
                "vwap_value": round(primary_value, 6),
                "vwap_distance_pct": round(distance, 4),
                "vwap_relation": relation,
                "vwap_anchor_mode": context["anchor_mode"],
                "vwap_anchor_time_et": (
                    context["anchor_time"].isoformat() if context["anchor_time"] is not None else None
                ),
                "premarket_vwap_value": (
                    round(context["premarket_value"], 6)
                    if context["premarket_value"] is not None
                    else None
                ),
                "vwap_history_start_time_et": "04:00",
                "vwap_bar_timeframe_source": (
                    f"{getattr(client, 'provider_name', 'market data provider')} 1Min bars; "
                    "primary VWAP anchored 09:30 ET after regular open"
                ),
                "vwap_reclaimed_last_10m": reclaimed,
                "vwap_reclaim_age_bars": reclaim_age,
                "timeframe_confirmations": confirmations,
                "timeframes": confirmation_details,
                **st_vwap_crossover_evidence(day),
                **_alignment_summary(
                    day,
                    primary_series,
                    client.bars_frame(current_session_30s_raw.get(symbol) or []),
                ),
            }
        )
        _rescore_record(record)
        corrected += 1

    # Rebuild cohort-relative attention after the corrected Evidence scores.  This is
    # local computation only; it does not repeat discovery or request provider data.
    if updated:
        try:
            from . import discovery

            updated = discovery.apply_attention_ranking(updated)
        except Exception:
            pass

    diagnostics = getattr(client, "diagnostics", None)
    if isinstance(diagnostics, dict):
        diagnostics["gs378_live_vwap_st_crossover"] = {
            "primary_vwap_policy": "09:30 ET RTH anchor after open; 04:00 ET only premarket",
            "supertrend_seed_policy": "current-day history retained for early flip detection",
            "crossover_timeframes": ["1m", "3m"],
            "crossover_source": "already-fetched stage6_current_session bars",
            "additional_history_requests": 0,
            "records_corrected": corrected,
        }
    return updated


def _inherit(wrapper, wrapped) -> None:
    for name, value in getattr(wrapped, "__dict__", {}).items():
        if name.startswith("_gs") and not hasattr(wrapper, name):
            setattr(wrapper, name, value)


def install() -> None:
    """Observe Stage-6's existing history call and replace 04:00-anchored VWAP evidence."""
    from . import discovery

    current = discovery.analyze_candidates
    if getattr(current, "_gs378_live_vwap_st_crossover", False):
        return

    @wraps(current)
    def analyze_with_live_vwap_truth(client, candidates, news_index, discovery_reasons):
        captured_1m: dict[str, list[dict]] = {}
        captured_30s: dict[str, list[dict]] = {}
        original_bars = getattr(client, "bars", None)
        patched = False
        had_instance_bars = False
        prior_instance_bars = None

        if callable(original_bars):
            instance_dict = getattr(client, "__dict__", None)
            if isinstance(instance_dict, dict):
                had_instance_bars = "bars" in instance_dict
                prior_instance_bars = instance_dict.get("bars")

            def capturing_bars(symbols, **kwargs):
                result = original_bars(symbols, **kwargs)
                reason = str(kwargs.get("history_reason") or "")
                timeframe = str(kwargs.get("timeframe") or "")
                if reason == "stage6_current_session" and timeframe.lower() in {"1min", "1m"}:
                    captured_1m.update(result or {})
                elif reason == "stage6_current_session_30s":
                    captured_30s.update(result or {})
                return result

            try:
                setattr(client, "bars", capturing_bars)
                patched = True
            except Exception:
                patched = False

        try:
            records = current(client, candidates, news_index, discovery_reasons)
        finally:
            if patched:
                try:
                    if had_instance_bars:
                        setattr(client, "bars", prior_instance_bars)
                    else:
                        delattr(client, "bars")
                except Exception:
                    try:
                        setattr(client, "bars", original_bars)
                    except Exception:
                        pass

        if not captured_1m:
            diagnostics = getattr(client, "diagnostics", None)
            if isinstance(diagnostics, dict):
                diagnostics["gs378_live_vwap_st_crossover"] = {
                    "status": "history observation unavailable",
                    "additional_history_requests": 0,
                }
            return records

        return apply_live_vwap_truth(records, captured_1m, captured_30s, client)

    _inherit(analyze_with_live_vwap_truth, current)
    analyze_with_live_vwap_truth._gs378_live_vwap_st_crossover = True
    analyze_with_live_vwap_truth._gs378_original = current
    discovery.analyze_candidates = analyze_with_live_vwap_truth

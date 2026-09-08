"""GS391: align Walter's primary VWAP with the Webull chart and expose ST parity evidence.

Live validation on 2026-09-08 proved that GS378's 09:30 ET VWAP reset did not
match the Webull chart used by the operator.  Webull continued to display a
cumulative extended-session VWAP while Walter re-anchored at 09:30, allowing a
symbol that was still materially below the operator's VWAP to become "above
VWAP" inside Walter.

GS391 corrects that decision-evidence mismatch:
* the primary VWAP remains cumulatively anchored at 04:00 ET through the day;
* an RTH-only 09:30 VWAP is retained as secondary diagnostics, not authority;
* all existing GS378 reclaim/crossover/alignment/rescoring logic therefore runs
  against the corrected primary VWAP without changing any thresholds;
* Walter's SuperTrend formula is NOT changed.  Latest 1m/3m OHLCV, VWAP and
  SuperTrend(10,3) line/state are persisted as OBSERVATIONAL_ONLY parity evidence
  so a later ST fix can be based on chart-for-chart proof rather than inference.

No additional market-data request is made and no execution/order logic changes.
"""
from __future__ import annotations

from functools import wraps
import math
from typing import Any

import pandas as pd

from . import gs378_live_vwap_st_crossover as gs378
from .indicators import session_vwap, supertrend

AUTHORITY = "OBSERVATIONAL_ONLY"
PRIMARY_POLICY = "WEBULL_EXTENDED_04:00_ET"


def _finite(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _last_vwap(frame: pd.DataFrame) -> float | None:
    if frame is None or frame.empty:
        return None
    series = session_vwap(frame)
    return _finite(series.iloc[-1]) if len(series) else None


def webull_primary_vwap_context(frame: pd.DataFrame | None) -> dict:
    """Return the extended-session VWAP used by the operator's Webull chart.

    Walter still fetches current-day history from 04:00 ET.  Unlike GS378, the
    primary cumulative series does not reset at 09:30 ET.  RTH-only VWAP remains
    available as a secondary diagnostic value.
    """
    day = gs378._eastern_day(frame)
    if day.empty:
        return {
            "day": day,
            "series": pd.Series(dtype=float),
            "value": None,
            "anchor_mode": "UNAVAILABLE",
            "anchor_time": None,
            "premarket_value": None,
            "rth_value": None,
        }

    premarket_start, regular_start = gs378._session_boundaries(day)
    extended = day[day.index >= premarket_start].copy()
    if extended.empty:
        extended = day.copy()
        anchor = day.index[0]
        mode = "FALLBACK_FIRST_AVAILABLE_BAR"
    else:
        anchor = premarket_start
        mode = PRIMARY_POLICY

    primary = session_vwap(extended)
    value = _finite(primary.iloc[-1]) if len(primary) else None

    premarket = day[(day.index >= premarket_start) & (day.index < regular_start)]
    premarket_value = _last_vwap(premarket)

    rth = day[day.index >= regular_start]
    rth_value = _last_vwap(rth)

    return {
        "day": day,
        "series": primary,
        "value": value,
        "anchor_mode": mode,
        "anchor_time": anchor,
        "premarket_value": premarket_value,
        "rth_value": rth_value,
    }


def _latest_timeframe_snapshot(context: dict, label: str) -> dict:
    day = context.get("day")
    primary = context.get("series")
    if day is None or day.empty or primary is None or primary.empty:
        return {}

    tf = gs378._timeframe_frame(day, label)
    if tf.empty:
        return {}
    tf_vwap = gs378._timeframe_vwap(primary, label).reindex(tf.index)
    st_line, trend = supertrend(tf, 10, 3)

    latest_time = tf.index[-1]
    row = tf.iloc[-1]
    close = _finite(row.get("close"))
    st_value = _finite(st_line.iloc[-1]) if len(st_line) else None
    vwap_value = _finite(tf_vwap.iloc[-1]) if len(tf_vwap) else None
    bullish = bool(trend.iloc[-1]) if len(trend) and pd.notna(trend.iloc[-1]) else None

    return {
        "timeframe": label,
        "bar_timestamp_et": latest_time.isoformat(),
        "open": _finite(row.get("open")),
        "high": _finite(row.get("high")),
        "low": _finite(row.get("low")),
        "close": close,
        "volume": _finite(row.get("volume")),
        "vwap_value": vwap_value,
        "above_vwap": bool(close is not None and vwap_value is not None and close >= vwap_value),
        "supertrend_10_3": st_value,
        "supertrend_bullish": bullish,
        "relation_to_supertrend": (
            "above" if close is not None and st_value is not None and close >= st_value
            else "below" if close is not None and st_value is not None
            else None
        ),
        "supertrend_ready": st_value is not None,
        "bar_count": len(tf),
    }


def _parity_observation(frame: pd.DataFrame, context: dict) -> dict:
    day = context.get("day")
    return {
        "authority": AUTHORITY,
        "primary_vwap_policy": PRIMARY_POLICY,
        "source_latest_1m_timestamp_et": (
            day.index[-1].isoformat() if day is not None and not day.empty else None
        ),
        "one_minute": _latest_timeframe_snapshot(context, "1m"),
        "three_minute": _latest_timeframe_snapshot(context, "3m"),
    }


def _build_scan_parity(records) -> dict:
    symbols = []
    for source in records or []:
        record = dict(source)
        observation = record.get("st_webull_parity_observation")
        if not isinstance(observation, dict) or not observation:
            continue
        symbols.append(
            {
                "symbol": str(record.get("symbol") or "").strip().upper(),
                "price": _finite(record.get("price")),
                "primary_vwap": _finite(record.get("vwap_value")),
                "vwap_distance_pct": _finite(record.get("vwap_distance_pct")),
                "vwap_anchor_mode": record.get("vwap_anchor_mode"),
                "premarket_vwap": _finite(record.get("premarket_vwap_value")),
                "rth_only_vwap": _finite(record.get("rth_vwap_value")),
                "parity": observation,
            }
        )
    return {
        "authority": AUTHORITY,
        "primary_vwap_policy": PRIMARY_POLICY,
        "symbol_count": len(symbols),
        "symbols": symbols,
    }


def install() -> None:
    """Install corrected primary VWAP plus observational 1m/3m ST evidence."""
    from . import flight_recorder, runtime_evidence

    current_primary = gs378.primary_vwap_context
    if not getattr(current_primary, "_gs391_webull_vwap", False):
        webull_primary_vwap_context._gs391_webull_vwap = True
        webull_primary_vwap_context._gs391_original = current_primary
        gs378.primary_vwap_context = webull_primary_vwap_context

    current_apply = gs378.apply_live_vwap_truth
    if not getattr(current_apply, "_gs391_webull_vwap", False):
        @wraps(current_apply)
        def apply_webull_vwap_truth(
            records,
            current_session_raw,
            current_session_30s_raw,
            client,
        ):
            updated = current_apply(
                records,
                current_session_raw,
                current_session_30s_raw,
                client,
            )
            for record in updated or []:
                symbol = str(record.get("symbol") or "").strip().upper()
                if not symbol:
                    continue
                raw_rows = (current_session_raw or {}).get(symbol) or []
                frame = client.bars_frame(raw_rows)
                context = webull_primary_vwap_context(frame)
                if context.get("value") is None:
                    continue
                record["webull_extended_vwap_value"] = round(float(context["value"]), 6)
                record["rth_vwap_value"] = (
                    round(float(context["rth_value"]), 6)
                    if context.get("rth_value") is not None
                    else None
                )
                record["vwap_bar_timeframe_source"] = (
                    f"{getattr(client, 'provider_name', 'market data provider')} 1Min bars; "
                    "primary VWAP cumulatively anchored 04:00 ET to match Webull extended-hours chart"
                )
                record["st_webull_parity_observation"] = _parity_observation(frame, context)

            diagnostics = getattr(client, "diagnostics", None)
            if isinstance(diagnostics, dict):
                diagnostics["gs391_webull_vwap_st_parity"] = {
                    "primary_vwap_policy": PRIMARY_POLICY,
                    "rth_vwap_role": "secondary diagnostics only",
                    "supertrend_formula_changed": False,
                    "supertrend_parity_evidence": ["1m", "3m"],
                    "additional_market_data_requests": 0,
                    "records_observed": sum(
                        1 for record in updated or []
                        if record.get("st_webull_parity_observation")
                    ),
                }
            return updated

        apply_webull_vwap_truth._gs391_webull_vwap = True
        apply_webull_vwap_truth._gs391_original = current_apply
        gs378.apply_live_vwap_truth = apply_webull_vwap_truth

    current_persist = flight_recorder.persist_replayable_scan
    if not getattr(current_persist, "_gs391_webull_vwap", False):
        @wraps(current_persist)
        def persist_replayable_scan(recorder, scan: dict, records, *args, **kwargs):
            parity = _build_scan_parity(records)
            if parity.get("symbol_count"):
                scan = dict(scan)
                scan["webull_vwap_st_parity"] = parity
            return current_persist(recorder, scan, records, *args, **kwargs)

        persist_replayable_scan._gs391_webull_vwap = True
        persist_replayable_scan._gs391_original = current_persist
        flight_recorder.persist_replayable_scan = persist_replayable_scan

    current_export = runtime_evidence.current_scan_export
    if not getattr(current_export, "_gs391_webull_vwap", False):
        @wraps(current_export)
        def current_scan_export(scan: dict | None) -> dict:
            payload = current_export(scan)
            if scan and scan.get("webull_vwap_st_parity"):
                payload = dict(payload)
                payload["webull_vwap_st_parity"] = runtime_evidence._safe(
                    scan.get("webull_vwap_st_parity")
                )
            return payload

        current_scan_export._gs391_webull_vwap = True
        current_scan_export._gs391_original = current_export
        runtime_evidence.current_scan_export = current_scan_export

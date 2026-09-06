"""GS386: persist incremental Webull 30-second observations for live validation.

This module is evidence-only. It does not alter discovery, scoring, readiness,
qualification, ranking, alerts, execution, candidate membership, or any ST/VWAP
trading authority. It snapshots only *completed* 30-second bars already produced
by GS379, annotates them with Walter's existing SuperTrend(10, 3.0) calculation,
and attaches only newly closed bars to the existing Flight Recorder export.
"""
from __future__ import annotations

from functools import wraps
from typing import Any

import pandas as pd

from .indicators import supertrend

AUTHORITY = "OBSERVATIONAL_ONLY"
BAR_INTERVAL_SECONDS = 30
ST_PERIOD = 10
ST_MULTIPLIER = 3.0


def _active_provider():
    """Return the process-local authoritative Webull provider, if one exists."""
    from . import gs379_webull_stream_data_truth as gs379

    ref = getattr(gs379, "_ACTIVE_PROVIDER_REF", None)
    return ref() if ref is not None else None


def _bar_frame(rows: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "open": [row.get("o") for row in rows],
            "high": [row.get("h") for row in rows],
            "low": [row.get("l") for row in rows],
            "close": [row.get("c") for row in rows],
            "volume": [row.get("v") for row in rows],
        }
    )


def _annotated_rows(rows: list[dict]) -> list[dict]:
    """Annotate completed bars with the existing ST(10,3) implementation."""
    if not rows:
        return []
    frame = _bar_frame(rows)
    st_line, trend = supertrend(frame, period=ST_PERIOD, multiplier=ST_MULTIPLIER)
    output: list[dict] = []
    for index, row in enumerate(rows):
        st_value = st_line.iloc[index] if index < len(st_line) else None
        ready = st_value is not None and not pd.isna(st_value)
        output.append(
            {
                "timestamp_ms": int(row.get("t")),
                "open": float(row.get("o")),
                "high": float(row.get("h")),
                "low": float(row.get("l")),
                "close": float(row.get("c")),
                "volume": float(row.get("v") or 0.0),
                "trade_count": int(row.get("trade_count") or 0),
                "supertrend_10_3": float(st_value) if ready else None,
                "supertrend_state": (
                    "bullish" if bool(trend.iloc[index]) else "bearish"
                ) if ready else None,
                "supertrend_ready": bool(ready),
            }
        )
    return output


def build_observational_30s(provider, symbols) -> dict[str, Any]:
    """Return only newly closed 30s bars since the prior recorder checkpoint."""
    if provider is None or not hasattr(provider, "stream_30s_bars"):
        return {
            "authority": AUTHORITY,
            "source": "Webull OpenAPI TICK",
            "bar_interval_seconds": BAR_INTERVAL_SECONDS,
            "supertrend": {"period": ST_PERIOD, "multiplier": ST_MULTIPLIER},
            "new_bar_count": 0,
            "symbol_count": 0,
            "symbols": [],
        }

    watermark = getattr(provider, "_gs386_last_recorded_30s_t", None)
    if watermark is None:
        watermark = {}
        provider._gs386_last_recorded_30s_t = watermark

    observations = []
    total_new = 0
    for raw_symbol in symbols or []:
        symbol = str(raw_symbol or "").strip().upper()
        if not symbol:
            continue
        rows = list(provider.stream_30s_bars(symbol) or [])
        if not rows:
            continue
        annotated = _annotated_rows(rows)
        last_recorded = int(watermark.get(symbol, -1))
        new_rows = [row for row in annotated if row["timestamp_ms"] > last_recorded]
        if not new_rows:
            continue
        watermark[symbol] = max(row["timestamp_ms"] for row in new_rows)
        total_new += len(new_rows)
        observations.append(
            {
                "symbol": symbol,
                "bar_count": len(new_rows),
                "latest_timestamp_ms": watermark[symbol],
                "bars": new_rows,
            }
        )

    diagnostics = getattr(provider, "diagnostics", {}).setdefault("webull_stream", {})
    diagnostics["thirty_second_observational_rows_recorded"] = int(
        diagnostics.get("thirty_second_observational_rows_recorded", 0)
    ) + total_new
    diagnostics["thirty_second_observational_symbols_recorded"] = len(observations)

    return {
        "authority": AUTHORITY,
        "source": "Webull OpenAPI TICK",
        "bar_interval_seconds": BAR_INTERVAL_SECONDS,
        "supertrend": {"period": ST_PERIOD, "multiplier": ST_MULTIPLIER},
        "new_bar_count": total_new,
        "symbol_count": len(observations),
        "symbols": observations,
    }


def _scan_symbols(scan: dict) -> list[str]:
    return [
        str(item.get("symbol") or "").strip().upper()
        for item in (scan.get("symbols") or [])
        if str(item.get("symbol") or "").strip()
    ]


def install() -> None:
    """Attach observational 30s evidence to existing recorder/export paths."""
    from . import flight_recorder, runtime_evidence

    current_persist = flight_recorder.persist_replayable_scan
    if not getattr(current_persist, "_gs386_30s_observational", False):
        @wraps(current_persist)
        def persist_replayable_scan(recorder, scan: dict, records, *args, **kwargs):
            provider = _active_provider()
            observational = build_observational_30s(provider, _scan_symbols(scan))
            if observational.get("new_bar_count"):
                scan = dict(scan)
                scan["observational_30s"] = observational
            return current_persist(recorder, scan, records, *args, **kwargs)

        persist_replayable_scan._gs386_30s_observational = True
        persist_replayable_scan._gs386_original = current_persist
        flight_recorder.persist_replayable_scan = persist_replayable_scan

    current_export = runtime_evidence.current_scan_export
    if not getattr(current_export, "_gs386_30s_observational", False):
        @wraps(current_export)
        def current_scan_export(scan: dict | None) -> dict:
            payload = current_export(scan)
            if scan and scan.get("observational_30s"):
                payload = dict(payload)
                payload["observational_30s"] = runtime_evidence._safe(
                    scan.get("observational_30s")
                )
            return payload

        current_scan_export._gs386_30s_observational = True
        current_scan_export._gs386_original = current_export
        runtime_evidence.current_scan_export = current_scan_export

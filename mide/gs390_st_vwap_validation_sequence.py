"""GS390: bind existing ST/VWAP events to genuine 30-second stream evidence.

This module is observational only.  It does not fetch market data and does not
alter discovery, scoring, readiness, qualification, ranking, alerts, execution,
or candidate membership.  GS378 already reconstructs deterministic 1m/3m
ST/VWAP crossover events from Walter's Stage-6 history; GS379/GS386 already hold
genuine Webull 30-second bars.  GS390 joins those existing facts in the Flight
Recorder so live validation can answer what happened before and after ignition.
"""
from __future__ import annotations

from datetime import datetime
from functools import wraps
from typing import Any

from .gs386_30s_observational_recorder import _annotated_rows

AUTHORITY = "OBSERVATIONAL_ONLY"
SOURCE = "GS378 ST/VWAP events + Webull OpenAPI TICK 30s bars"


def _number(value: Any) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _event(record: dict, label: str) -> dict:
    events = record.get("st_vwap_cross_events") or {}
    value = events.get(label) if isinstance(events, dict) else None
    return dict(value) if isinstance(value, dict) else {}


def _timeframe_state(record: dict, label: str) -> dict:
    states = record.get("timeframes") or {}
    value = states.get(label) if isinstance(states, dict) else None
    if not isinstance(value, dict):
        return {}
    return {
        "above_vwap": bool(value.get("above_vwap")),
        "supertrend_bullish": bool(value.get("supertrend")),
    }


def _timestamp_ms(value: Any) -> int | None:
    if value is None:
        return None
    try:
        text = str(value).replace("Z", "+00:00")
        return int(datetime.fromisoformat(text).timestamp() * 1000)
    except (TypeError, ValueError, OverflowError):
        return None


def _thirty_second_snapshot(row: dict | None) -> dict | None:
    if not row:
        return None
    close = _number(row.get("close"))
    st_value = _number(row.get("supertrend_10_3"))
    distance = None
    if close is not None and st_value not in (None, 0):
        distance = (close - st_value) / st_value * 100.0
    relation = None
    if close is not None and st_value is not None:
        relation = "above" if close >= st_value else "below"
    return {
        "timestamp_ms": row.get("timestamp_ms"),
        "close": close,
        "volume": _number(row.get("volume")),
        "trade_count": row.get("trade_count"),
        "supertrend_10_3": st_value,
        "supertrend_state": row.get("supertrend_state"),
        "supertrend_ready": bool(row.get("supertrend_ready")),
        "relation_to_supertrend": relation,
        "distance_to_supertrend_pct": round(distance, 4) if distance is not None else None,
    }


def _thirty_second_context(provider, symbol: str, ignition_ms: int | None) -> dict:
    if provider is None or not hasattr(provider, "stream_30s_bars"):
        return {"at_or_before_1m_ignition": None, "latest_closed": None}
    rows = list(provider.stream_30s_bars(symbol) or [])
    annotated = _annotated_rows(rows)
    if not annotated:
        return {"at_or_before_1m_ignition": None, "latest_closed": None}
    before = None
    if ignition_ms is not None:
        eligible = [
            row for row in annotated
            if int(row.get("timestamp_ms") or -1) <= ignition_ms
        ]
        before = eligible[-1] if eligible else None
    return {
        "at_or_before_1m_ignition": _thirty_second_snapshot(before),
        "latest_closed": _thirty_second_snapshot(annotated[-1]),
    }


def _confirmation_delay_seconds(one_minute: dict, three_minute: dict) -> float | None:
    one_ms = _timestamp_ms(one_minute.get("timestamp"))
    three_ms = _timestamp_ms(three_minute.get("timestamp"))
    if one_ms is None or three_ms is None:
        return None
    return round((three_ms - one_ms) / 1000.0, 1)


def _sequence_label(one_minute: dict, three_minute: dict) -> str:
    one_recent = bool(one_minute.get("recent"))
    three_recent = bool(three_minute.get("recent"))
    if one_recent and three_recent:
        return "1m ignition -> 3m confirmation observed"
    if one_recent:
        return "1m ignition observed; 3m confirmation not yet recent"
    if three_recent:
        return "3m confirmation recent; 1m ignition outside recent window"
    return "no recent ST/VWAP crossover"


def build_validation_sequence(scan: dict, records, provider) -> dict:
    """Build detached live-validation rows from evidence Walter already computed."""
    output = []
    for source in records or []:
        record = dict(source)
        symbol = str(record.get("symbol") or "").strip().upper()
        if not symbol:
            continue
        one_minute = _event(record, "1m")
        three_minute = _event(record, "3m")
        if not (one_minute.get("recent") or three_minute.get("recent")):
            continue

        current_price = _number(record.get("price"))
        ignition_price = _number(one_minute.get("price"))
        response = None
        if current_price is not None and ignition_price not in (None, 0):
            response = (current_price - ignition_price) / ignition_price * 100.0
        ignition_ms = _timestamp_ms(one_minute.get("timestamp"))

        output.append(
            {
                "symbol": symbol,
                "sequence": _sequence_label(one_minute, three_minute),
                "scan_price": current_price,
                "participation_score": _number(record.get("participation_score")),
                "participation_surge_score": _number(
                    record.get("participation_surge_score")
                ),
                "volume_pace_ratio": _number(record.get("volume_pace_ratio")),
                "participation_gate": dict(record.get("participation_gate") or {}),
                "thirty_second": _thirty_second_context(provider, symbol, ignition_ms),
                "one_minute": {
                    "current_state": _timeframe_state(record, "1m"),
                    "cross": one_minute,
                },
                "three_minute": {
                    "current_state": _timeframe_state(record, "3m"),
                    "cross": three_minute,
                },
                "confirmation_delay_seconds": _confirmation_delay_seconds(
                    one_minute, three_minute
                ),
                "price_response_since_1m_ignition_pct": (
                    round(response, 4) if response is not None else None
                ),
            }
        )

    return {
        "authority": AUTHORITY,
        "source": SOURCE,
        "scan_id": scan.get("scan_id"),
        "scan_timestamp": scan.get("timestamp"),
        "symbol_count": len(output),
        "symbols": output,
    }


def _active_provider():
    from .gs386_30s_observational_recorder import _active_provider as active_provider

    return active_provider()


def install() -> None:
    """Attach GS390 validation evidence to recorder/export paths only."""
    from . import flight_recorder, runtime_evidence

    current_persist = flight_recorder.persist_replayable_scan
    if not getattr(current_persist, "_gs390_st_vwap_validation", False):
        @wraps(current_persist)
        def persist_replayable_scan(recorder, scan: dict, records, *args, **kwargs):
            sequence = build_validation_sequence(scan, records, _active_provider())
            if sequence.get("symbol_count"):
                scan = dict(scan)
                scan["st_vwap_validation_sequence"] = sequence
            return current_persist(recorder, scan, records, *args, **kwargs)

        persist_replayable_scan._gs390_st_vwap_validation = True
        persist_replayable_scan._gs390_original = current_persist
        flight_recorder.persist_replayable_scan = persist_replayable_scan

    current_export = runtime_evidence.current_scan_export
    if not getattr(current_export, "_gs390_st_vwap_validation", False):
        @wraps(current_export)
        def current_scan_export(scan: dict | None) -> dict:
            payload = current_export(scan)
            if scan and scan.get("st_vwap_validation_sequence"):
                payload = dict(payload)
                payload["st_vwap_validation_sequence"] = runtime_evidence._safe(
                    scan.get("st_vwap_validation_sequence")
                )
            return payload

        current_scan_export._gs390_st_vwap_validation = True
        current_scan_export._gs390_original = current_export
        runtime_evidence.current_scan_export = current_scan_export

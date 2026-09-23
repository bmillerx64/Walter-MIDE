"""Authoritative Walter Next Replay / Validation boundary.

Stable recorder/outcome classes remain direct imports. Replaceable validation
functions resolve dynamically so warm Streamlit reruns cannot retain stale wrappers.
"""

from __future__ import annotations

from mide.flight_recorder import FlightRecorder
from mide.mission_outcomes import MissionOutcomeStore


def _validation_number(
    record: dict,
    *keys: str,
    default: float | None = None,
) -> float | None:
    for key in keys:
        value = record.get(key)
        if value is None or value == "":
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return default


def build_validation_sequence_with_ignition(
    original,
    scan: dict,
    records,
    provider,
) -> dict:
    """Enrich GS390 replay output with authoritative primary-ignition truth."""
    from mide import gs390_st_vwap_validation_sequence as sequence
    from mide.authorities import market_evidence

    payload = original(scan, records, provider)
    payload = dict(payload)
    rows = [dict(item) for item in list(payload.get("symbols") or [])]
    by_symbol = {
        str(item.get("symbol") or "").upper(): item
        for item in rows
        if str(item.get("symbol") or "").strip()
    }

    for source in records or []:
        record = dict(source)
        symbol = str(record.get("symbol") or "").strip().upper()
        if not symbol:
            continue
        ignition = market_evidence.ignition_evidence(record)
        if not ignition.get("recent") and symbol not in by_symbol:
            continue

        row = by_symbol.get(symbol)
        if row is None:
            one = sequence._event(record, "1m")
            three = sequence._event(record, "3m")
            row = {
                "symbol": symbol,
                "scan_price": _validation_number(record, "price"),
                "participation_score": _validation_number(
                    record,
                    "participation_score",
                ),
                "participation_surge_score": _validation_number(
                    record,
                    "participation_surge_score",
                ),
                "volume_pace_ratio": _validation_number(
                    record,
                    "volume_pace_ratio",
                ),
                "participation_gate": dict(record.get("participation_gate") or {}),
                "thirty_second": sequence._thirty_second_context(
                    provider,
                    symbol,
                    sequence._timestamp_ms(one.get("bullish_flip_timestamp")),
                ),
                "one_minute": {
                    "current_state": sequence._timeframe_state(record, "1m"),
                    "literal_st_line_vwap_cross": one,
                },
                "three_minute": {
                    "current_state": sequence._timeframe_state(record, "3m"),
                    "literal_st_line_vwap_cross": three,
                },
                "price_response_since_1m_ignition_pct": None,
            }
            rows.append(row)
            by_symbol[symbol] = row

        row["operator_ignition"] = ignition
        if ignition.get("recent"):
            row["sequence"] = (
                "1m price/VWAP + bullish SuperTrend ignition observed; "
                + (
                    "3m confirmation present"
                    if ignition.get("three_minute_confirmation")
                    else "3m confirmation pending"
                )
            )
        row["literal_st_line_vwap_cross_role"] = "SECONDARY_MATURATION_EVIDENCE"

    payload["symbols"] = rows
    payload["symbol_count"] = len(rows)
    payload["primary_ignition_definition"] = (
        "fresh VWAP reclaim/hold + bullish 1m SuperTrend, or fresh bullish 1m "
        "SuperTrend flip while price is above VWAP and inside the +2% chase guard"
    )
    payload["three_minute_role"] = "CONFIRMATION_NOT_PERMISSION"
    return payload


def install_ignition_validation_sequence() -> None:
    """Bind GS393 replay enrichment at its historical recorder install position."""
    from mide import gs390_st_vwap_validation_sequence as sequence

    current = sequence.build_validation_sequence
    if getattr(current, "_gs393_ignition_truth", False):
        return

    def build_with_ignition(scan: dict, records, provider) -> dict:
        return build_validation_sequence_with_ignition(
            current,
            scan,
            records,
            provider,
        )

    build_with_ignition._gs393_ignition_truth = True
    build_with_ignition._gs393_original = current
    sequence.build_validation_sequence = build_with_ignition


def prefilter_decision(*args, **kwargs):
    from mide import flight_recorder
    return flight_recorder.prefilter_decision(*args, **kwargs)


def scan_integrity_report(*args, **kwargs):
    from mide import data_integrity
    return data_integrity.scan_integrity_report(*args, **kwargs)


__all__ = [
    "FlightRecorder",
    "install_ignition_validation_sequence",
    "build_validation_sequence_with_ignition",
    "MissionOutcomeStore",
    "prefilter_decision",
    "scan_integrity_report",
]

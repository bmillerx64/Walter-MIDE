"""Read-only live market evidence audit for Walter candidates.

GS241 asks whether a candidate contains enough fresh, internally coherent market
evidence to trust downstream decisions. It never changes qualification, ranking,
scoring, entry readiness, alerts, or execution policy.
"""
from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any

CORE_FIELDS = ("price", "volume")
DECISION_FIELDS = ("vwap_value", "supertrend_bullish")


def _present(value: object) -> bool:
    return value is not None and value != ""


def _utc_datetime(value: object) -> datetime | None:
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, str) and value:
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def market_evidence_report(record: Mapping[str, Any], *, scan_timestamp: datetime | str | None = None, max_age_seconds: float = 120.0) -> dict[str, object]:
    """Return deterministic completeness, freshness, and coherence diagnostics."""
    missing = [field for field in CORE_FIELDS + DECISION_FIELDS if not _present(record.get(field))]
    source_timestamp = record.get("source_bar_timestamp") or record.get("last_bar_timestamp") or record.get("bar_timestamp")
    source_dt = _utc_datetime(source_timestamp)
    scan_dt = _utc_datetime(scan_timestamp) or datetime.now(timezone.utc)
    explicit_age = record.get("source_bar_age")
    if explicit_age is None:
        explicit_age = record.get("bar_age_seconds")
    try:
        age_seconds = float(explicit_age) if explicit_age is not None else None
    except (TypeError, ValueError):
        age_seconds = None
    if age_seconds is None and source_dt is not None:
        age_seconds = max(0.0, (scan_dt - source_dt).total_seconds())
    if source_dt is None:
        missing.append("source_bar_timestamp")
    fresh = age_seconds is not None and age_seconds <= max_age_seconds

    timeframes = record.get("timeframes")
    alignment = record.get("timeframe_alignment")
    timeframe_evidence_present = bool(timeframes) or bool(alignment)
    if not timeframe_evidence_present:
        missing.append("timeframe_evidence")

    coherence_failures: list[str] = []
    for field in ("price", "vwap_value"):
        value = record.get(field)
        if _present(value):
            try:
                if float(value) <= 0:
                    coherence_failures.append(f"{field}_nonpositive")
            except (TypeError, ValueError):
                coherence_failures.append(f"{field}_invalid")
    if _present(record.get("volume")):
        try:
            if float(record.get("volume")) < 0:
                coherence_failures.append("volume_negative")
        except (TypeError, ValueError):
            coherence_failures.append("volume_invalid")

    missing = sorted(set(missing))
    required_count = len(CORE_FIELDS) + len(DECISION_FIELDS) + 2
    completeness_pct = round(max(0, required_count - len(missing)) / required_count * 100, 1)
    if not missing and not coherence_failures and fresh:
        status = "TRUSTED"
    elif completeness_pct < 67 or coherence_failures:
        status = "INSUFFICIENT"
    else:
        status = "CAUTION"

    return {
        "symbol": str(record.get("symbol") or "").upper(),
        "status": status,
        "trusted": status == "TRUSTED",
        "completeness_pct": completeness_pct,
        "missing_fields": missing,
        "coherence_failures": coherence_failures,
        "source_bar_timestamp": source_timestamp,
        "source_bar_age_seconds": age_seconds,
        "freshness_measured": age_seconds is not None,
        "fresh": fresh,
        "max_age_seconds": float(max_age_seconds),
        "timeframe_evidence_present": timeframe_evidence_present,
        "price": record.get("price"),
        "volume": record.get("volume"),
        "vwap_value": record.get("vwap_value"),
        "supertrend_bullish": record.get("supertrend_bullish"),
    }


def market_evidence_summary(record: Mapping[str, Any], **kwargs: Any) -> str:
    report = market_evidence_report(record, **kwargs)
    age = report["source_bar_age_seconds"]
    age_text = "age N/A" if age is None else f"age {age:.0f}s"
    return f"Market evidence {report['status']} · {report['completeness_pct']:.0f}% · {age_text}"

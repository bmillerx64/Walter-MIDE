"""GS251 read-only market truth and cross-layer reconciliation diagnostics.

This module compares already-produced candidate evidence with Flight Recorder
state. It does not fetch data and has no authority over discovery, filtering,
qualification, ranking, scoring, alerts, or execution.
"""
from __future__ import annotations

from datetime import datetime, timezone
from collections.abc import Mapping, Sequence
from typing import Any


def _number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _timestamp(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        dt = value
    else:
        try:
            dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _first(record: Mapping[str, Any], *keys: str) -> Any:
    for key in keys:
        if record.get(key) is not None:
            return record.get(key)
    return None


def _flight_symbol_map(flight: Mapping[str, Any] | None) -> dict[str, Mapping[str, Any]]:
    if not isinstance(flight, Mapping):
        return {}
    rows = flight.get("symbols")
    if not isinstance(rows, Sequence) or isinstance(rows, (str, bytes)):
        return {}
    return {
        str(row.get("symbol") or "").upper(): row
        for row in rows
        if isinstance(row, Mapping) and row.get("symbol")
    }


def _event_passed(flight_row: Mapping[str, Any] | None, stage: str) -> bool | None:
    if not isinstance(flight_row, Mapping):
        return None
    events = flight_row.get("events")
    if not isinstance(events, Sequence) or isinstance(events, (str, bytes)):
        return None
    for event in reversed(events):
        if isinstance(event, Mapping) and str(event.get("stage") or "").lower() == stage.lower():
            passed = event.get("passed")
            return bool(passed) if passed is not None else None
    return None


def market_truth_row(
    record: Mapping[str, Any],
    *,
    scan_timestamp: Any = None,
    flight_row: Mapping[str, Any] | None = None,
    price_tolerance_pct: float = 1.0,
    pct_change_tolerance: float = 0.5,
) -> dict[str, Any]:
    """Return one detached diagnostic truth row for an already-produced candidate."""
    symbol = str(record.get("symbol") or "").upper()
    price = _number(_first(record, "price", "last_price", "close"))
    snapshot_price = _number(_first(record, "snapshot_price", "quote_price"))
    last_bar_close = _number(_first(record, "last_bar_close", "source_bar_close"))
    previous_close = _number(_first(record, "previous_close", "prev_close", "prev_close_price"))
    pct_change = _number(_first(record, "pct_change", "percent_change", "change_pct"))
    volume = _number(_first(record, "volume", "session_volume"))
    source_bar_timestamp = _first(record, "source_bar_timestamp", "bar_timestamp", "last_bar_timestamp")
    source_dt = _timestamp(source_bar_timestamp)
    scan_dt = _timestamp(scan_timestamp)
    age_seconds = None
    if source_dt is not None and scan_dt is not None:
        age_seconds = max(0.0, (scan_dt - source_dt).total_seconds())

    issues: list[str] = []
    if not symbol:
        issues.append("missing_symbol")
    if price is None or price <= 0:
        issues.append("missing_or_invalid_price")
    if volume is None or volume < 0:
        issues.append("missing_or_invalid_volume")
    if source_dt is None:
        issues.append("missing_or_invalid_source_timestamp")

    price_reference = snapshot_price if snapshot_price is not None else price
    if price_reference and last_bar_close and price_reference > 0:
        divergence = abs(last_bar_close - price_reference) / price_reference * 100.0
        if divergence > price_tolerance_pct:
            issues.append("snapshot_bar_price_mismatch")
    else:
        divergence = None

    calculated_pct_change = None
    if price is not None and previous_close not in (None, 0):
        calculated_pct_change = (price / previous_close - 1.0) * 100.0
        if pct_change is not None and abs(calculated_pct_change - pct_change) > pct_change_tolerance:
            issues.append("pct_change_mismatch")

    entry_ready = bool(_first(record, "entry_ready", "qualified_for_entry"))
    candidate_state = str(_first(record, "candidate_status", "decision_state", "workflow_state") or "")
    ranked = _first(record, "rank", "mission_rank") is not None
    elevated = entry_ready or ranked or candidate_state.lower() in {
        "entry ready", "entry_ready", "strengthening", "escalating", "primary", "secondary", "focus"
    }

    flight_qualified = _event_passed(flight_row, "qualified_for_ranking")
    flight_displayed = _event_passed(flight_row, "actionable display")
    if elevated and flight_qualified is False:
        issues.append("candidate_flight_qualification_mismatch")
    if ranked and flight_displayed is False:
        issues.append("candidate_flight_display_mismatch")

    return {
        "symbol": symbol,
        "price": price,
        "snapshot_price": snapshot_price,
        "last_bar_close": last_bar_close,
        "previous_close": previous_close,
        "reported_pct_change": pct_change,
        "calculated_pct_change": None if calculated_pct_change is None else round(calculated_pct_change, 4),
        "volume": volume,
        "vwap": _number(_first(record, "vwap_value", "vwap")),
        "supertrend_bullish": _first(record, "supertrend_bullish", "supertrend_state"),
        "source_bar_timestamp": source_dt.isoformat() if source_dt else None,
        "source_bar_age_seconds": None if age_seconds is None else round(age_seconds, 3),
        "price_divergence_pct": None if divergence is None else round(divergence, 4),
        "candidate_state": candidate_state,
        "entry_ready": entry_ready,
        "ranked": ranked,
        "flight_qualified_for_ranking": flight_qualified,
        "flight_actionable_display": flight_displayed,
        "issues": issues,
        "reconciled": not issues,
    }


def market_truth_reconciliation(
    records: Sequence[Mapping[str, Any]],
    *,
    scan_timestamp: Any = None,
    flight_snapshot: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Reconcile completed candidate records with Flight Recorder evidence."""
    flight_rows = _flight_symbol_map(flight_snapshot)
    rows = [
        market_truth_row(
            record,
            scan_timestamp=scan_timestamp,
            flight_row=flight_rows.get(str(record.get("symbol") or "").upper()),
        )
        for record in records
        if isinstance(record, Mapping)
    ]
    contradiction_rows = [row for row in rows if row["issues"]]
    issue_counts: dict[str, int] = {}
    for row in contradiction_rows:
        for issue in row["issues"]:
            issue_counts[issue] = issue_counts.get(issue, 0) + 1

    flight_funnel = dict(flight_snapshot.get("funnel") or {}) if isinstance(flight_snapshot, Mapping) else {}
    published_count = len(rows)
    flight_qualified = flight_funnel.get("Qualified")
    flight_displayed = flight_funnel.get("Displayed")
    funnel_issues: list[str] = []
    if published_count and flight_qualified is not None and int(flight_qualified or 0) != published_count:
        funnel_issues.append("published_vs_flight_qualified_count_mismatch")
    if published_count and flight_displayed is not None and int(flight_displayed or 0) != published_count:
        funnel_issues.append("published_vs_flight_displayed_count_mismatch")

    return {
        "records_audited": published_count,
        "reconciled_records": sum(1 for row in rows if row["reconciled"]),
        "contradictory_records": len(contradiction_rows),
        "reconciled_pct": round(sum(1 for row in rows if row["reconciled"]) / published_count * 100, 1) if published_count else None,
        "issue_counts": issue_counts,
        "funnel_issues": funnel_issues,
        "flight_funnel": flight_funnel,
        "rows": rows,
        "status": "UNMEASURED" if not rows else ("RECONCILED" if not contradiction_rows and not funnel_issues else "CONTRADICTIONS"),
    }


def market_truth_summary(report: Mapping[str, Any]) -> str:
    pct = report.get("reconciled_pct")
    pct_text = "N/A" if pct is None else f"{float(pct):.1f}%"
    return (
        f"Market truth: {report.get('status', 'UNMEASURED')} · "
        f"{int(report.get('records_audited', 0) or 0)} records · "
        f"{pct_text} reconciled · "
        f"{int(report.get('contradictory_records', 0) or 0)} contradictory"
    )

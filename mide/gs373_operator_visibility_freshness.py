"""GS373: keep stale or clearly failed structures off Walter's operator surface.

The scanner and ranked record remain intact for diagnostics/history.  This module
only narrows the records returned by ``ui.actionable_candidate_records`` for the
trader-facing workflow.

Live 2026-09-03 evidence showed FAMI still rendered as DEVELOPING while trading
roughly 7% below VWAP, and Walter's indicator record could briefly lag the live
chart during a fast flush.  Earlier GS342 intentionally left far-below-VWAP names
visible as DEVELOPING; that is too permissive for the operator surface.

GS373 therefore hides a record from the operator workflow when either:
* it is more than 2% below VWAP; or
* its source 1-minute bar is older than the existing 120-second market-evidence
  freshness contract.

Near-VWAP reclaim watches remain eligible, as do above-VWAP extended CHASE / WAIT
names.  Discovery, scanner membership, scoring, ranking, qualification, readiness,
alerts' underlying evidence, execution, and orders are unchanged.
"""
from __future__ import annotations

MAX_BELOW_VWAP_RECLAIM_DISTANCE_PCT = 2.0
MAX_OPERATOR_BAR_AGE_SECONDS = 120.0


def _number(record: dict, *keys: str) -> float | None:
    for key in keys:
        value = record.get(key)
        if value is None:
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return None


def operator_visibility_reason(record: dict) -> str:
    """Return the operator-only suppression reason, or an empty string."""
    distance = _number(record, "vwap_distance_pct")
    if distance is not None and distance < -MAX_BELOW_VWAP_RECLAIM_DISTANCE_PCT:
        return (
            f"{abs(distance):.1f}% below VWAP exceeds the "
            f"{MAX_BELOW_VWAP_RECLAIM_DISTANCE_PCT:.0f}% reclaim-watch window"
        )

    bar_age = _number(record, "source_bar_age_seconds", "source_bar_age", "bar_age_seconds")
    if bar_age is not None and bar_age > MAX_OPERATOR_BAR_AGE_SECONDS:
        return (
            f"source bar is {bar_age:.0f}s old; operator freshness limit is "
            f"{MAX_OPERATOR_BAR_AGE_SECONDS:.0f}s"
        )
    return ""


def operator_visible(record: dict) -> bool:
    """Whether a scanner-qualified record is current enough for the live screen."""
    return not operator_visibility_reason(record)


def install() -> None:
    """Install the operator-only visibility filter before app.py binds UI helpers."""
    from . import ui

    current = ui.actionable_candidate_records
    if getattr(current, "_gs373_operator_visibility_freshness", False):
        return

    def current_operator_records(records: list[dict]) -> list[dict]:
        return [record for record in current(records) if operator_visible(record)]

    for name, value in getattr(current, "__dict__", {}).items():
        if name.startswith("_gs") and not hasattr(current_operator_records, name):
            setattr(current_operator_records, name, value)
    current_operator_records._gs373_operator_visibility_freshness = True
    current_operator_records._gs373_original = current
    ui.actionable_candidate_records = current_operator_records

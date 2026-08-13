"""Read-only evidence trust diagnostics for Walter Mission outcomes.

GS240 checks whether a completed Mission outcome contains enough recorded market
observations to support its classification and attribution. It never changes
candidate qualification, ranking, scoring, entry readiness, alerts, or execution.
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

IDENTITY_FIELDS = ("outcome_id", "symbol", "first_mission_timestamp", "initial_price")
ENTRY_FIELDS = ("entry_ready_timestamp", "entry_ready_price")
EXCURSION_FIELDS = ("maximum_favorable_excursion", "maximum_adverse_excursion")
COMPLETION_FIELDS = ("classification", "closing_outcome")


def _present(value: object) -> bool:
    return value is not None and value != ""


def outcome_evidence_report(record: Mapping[str, Any]) -> dict[str, object]:
    """Return deterministic completeness diagnostics for one Mission outcome.

    The input mapping is never mutated. A field is required only when the
    lifecycle makes that evidence relevant; for example entry price/timestamp
    and excursions are required only when the candidate became Entry Ready.
    """
    required = list(IDENTITY_FIELDS)
    completed = record.get("completed") is True
    triggered = record.get("became_entry_ready") is True

    if completed:
        required.extend(COMPLETION_FIELDS)
    if triggered:
        required.extend(ENTRY_FIELDS)
        required.extend(EXCURSION_FIELDS)

    missing = [field for field in required if not _present(record.get(field))]

    observations = record.get("observations")
    observations_present = isinstance(observations, list) and len(observations) > 0
    if not observations_present:
        missing.append("observations")

    closing = record.get("closing_outcome")
    closing_price_present = isinstance(closing, Mapping) and _present(closing.get("price"))
    if completed and not closing_price_present:
        missing.append("closing_outcome.price")

    expected = len(required) + 1 + (1 if completed else 0)
    missing = sorted(set(missing))
    passed = max(0, expected - len(missing))
    completeness = round((passed / expected) * 100, 1) if expected else 100.0

    if completeness >= 99:
        status = "COMPLETE"
    elif completeness >= 80:
        status = "PARTIAL"
    else:
        status = "INSUFFICIENT"

    return {
        "outcome_id": record.get("outcome_id"),
        "symbol": str(record.get("symbol") or "").upper(),
        "status": status,
        "completeness_pct": completeness,
        "missing_fields": missing,
        "observations_present": observations_present,
        "closing_price_present": closing_price_present,
        "triggered": triggered,
        "completed": completed,
        "evidence_complete": status == "COMPLETE",
    }


def outcome_evidence_summary(record: Mapping[str, Any]) -> str:
    report = outcome_evidence_report(record)
    return f"Outcome evidence {report['status']} · {report['completeness_pct']:.0f}%"

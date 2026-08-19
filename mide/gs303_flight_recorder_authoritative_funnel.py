"""GS303: make Flight Recorder diagnostics follow the authoritative architecture ledger.

Diagnostic compatibility only.  The live scanner no longer emits the legacy
``participation_gate``, ``structure_gate`` and ``qualified_for_ranking`` fields
that FlightRecorder historically counted.  Reconstruct those recorder-only
views from WalterArchitectureV1's audit trail on detached record copies.
"""

from __future__ import annotations

from typing import Mapping


def _stage_audit(record: Mapping[str, object], stage: str) -> Mapping[str, object] | None:
    audits = record.get("architecture_audit") or []
    if not isinstance(audits, (list, tuple)):
        return None
    for row in reversed(audits):
        if isinstance(row, Mapping) and str(row.get("stage") or "") == stage:
            return row
    return None


def _gate_from_audit(audit: Mapping[str, object] | None) -> dict[str, object]:
    if not audit:
        return {}
    passed = str(audit.get("decision") or "").lower() == "qualified"
    reason = str(audit.get("reason") or "")
    return {
        "passed": passed,
        "reason": reason if passed else "",
        "failed_reasons": [] if passed or not reason else [reason],
        "checks": [],
        "source": "architecture_audit",
    }


def recorder_records(records) -> list[dict]:
    """Return detached recorder records synchronized to Architecture v1 outcomes."""
    synchronized: list[dict] = []
    for record in records:
        copied = dict(record)
        audits = copied.get("architecture_audit")
        if isinstance(audits, (list, tuple)) and audits:
            copied["participation_gate"] = _gate_from_audit(
                _stage_audit(copied, "Participation Assessment")
            )
            copied["structure_gate"] = _gate_from_audit(
                _stage_audit(copied, "Expansion Assessment")
            )
            copied["qualified_for_ranking"] = bool(
                str(copied.get("terminal_outcome") or "") == "Qualified and Ranked"
                or copied.get("mission_rank") is not None
            )
        synchronized.append(copied)
    return synchronized


def install() -> None:
    """Install a recorder-only compatibility boundary once per interpreter."""
    from .flight_recorder import FlightRecorder

    current = FlightRecorder.record_scan
    if getattr(current, "_gs303_authoritative_funnel", False):
        return

    original = current

    def record_scan(self, *args, **kwargs):
        if "records" in kwargs:
            kwargs = dict(kwargs)
            kwargs["records"] = recorder_records(kwargs["records"])
        return original(self, *args, **kwargs)

    record_scan._gs303_authoritative_funnel = True
    record_scan._gs303_original = original
    FlightRecorder.record_scan = record_scan

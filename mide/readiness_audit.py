"""Diagnostic-only readiness consistency telemetry."""
from __future__ import annotations


def readiness_consistency(record: dict) -> dict:
    state = record.get("candidate_status") or record.get("status")
    workflow_ready = state in {"Entry Ready", "EXCEPTIONAL"}
    trigger = record.get("trigger_diagnostics") or {}
    trigger_known = trigger.get("passed") is not None
    trigger_ready = trigger.get("passed") is True if trigger_known else None
    entry_actionable = record.get("entry_actionable")
    actionable_known = entry_actionable is not None
    current_ready = bool(entry_actionable) if actionable_known else trigger_ready
    mismatch = bool(workflow_ready and current_ready is False)
    return {
        "workflow_entry_ready": workflow_ready,
        "current_entry_evidence_known": actionable_known or trigger_known,
        "current_entry_evidence_ready": current_ready,
        "entry_readiness_mismatch": mismatch,
        "entry_readiness_audit": "workflow-ready/current-evidence-not-ready" if mismatch else "consistent-or-unknown",
    }


def enrich_records(records) -> None:
    for record in records or []:
        record.update(readiness_consistency(record))


def install() -> None:
    from . import flight_recorder
    original = flight_recorder.FlightRecorder.record_scan
    if getattr(original, "_gs235_readiness_audit", False):
        return

    def audited_record_scan(self, *args, **kwargs):
        records = kwargs.get("records")
        if records is not None:
            copied_records = [dict(record) for record in records]
            enrich_records(copied_records)
            kwargs = dict(kwargs)
            kwargs["records"] = copied_records
        return original(self, *args, **kwargs)

    audited_record_scan._gs235_readiness_audit = True
    flight_recorder.FlightRecorder.record_scan = audited_record_scan

"""GS422: keep GS421 convergence learning off Walter's hot path.

GS421 intentionally added observational 30s/1m/3m/5m/10m/15m maturation evidence,
but live Sep. 10 validation showed that computing the full stack for every analyzed
record materially lengthened scans. GS422 preserves the learning layer while only
running the expensive maturation reconstruction for records already showing a reason
to study them: watch/entry qualification, a 30s investigation tripwire, a recent
1m/3m ST/VWAP event, or an already-strengthening workflow state.

This module changes no discovery, scoring, ranking, qualification, readiness, VWAP or
chase guard, alert/audio, execution, order, or provider behavior.
"""
from __future__ import annotations

from functools import wraps

from . import gs421_multitimeframe_convergence_recorder as gs421

AUTHORITY = "OBSERVATIONAL_ONLY"
STUDY_STATES = {"STRENGTHENING", "ENTRY READY", "ENTRY_READY"}


def should_record_maturation(record: dict) -> bool:
    """Return whether this record has current signal worth expensive maturation study."""
    if not isinstance(record, dict):
        return False
    if bool(record.get("qualified_for_watch")) or bool(record.get("qualified_for_entry")):
        return True
    if bool(record.get("operator_investigation_tripwire")):
        return True
    if bool(record.get("st_vwap_cross_recent")) or bool(record.get("st_vwap_cross_new")):
        return True
    state = str(record.get("candidate_status") or record.get("status") or "").strip().upper()
    return state in STUDY_STATES


def skipped_evidence(record: dict) -> dict:
    """Record that GS421 was intentionally skipped rather than silently absent."""
    return {
        "authority": AUTHORITY,
        "source": gs421.SOURCE,
        "available": False,
        "skipped": True,
        "skip_reason": "no current convergence-study signal",
        "selection": {
            "qualified_for_watch": bool(record.get("qualified_for_watch")),
            "qualified_for_entry": bool(record.get("qualified_for_entry")),
            "operator_investigation_tripwire": bool(
                record.get("operator_investigation_tripwire")
            ),
            "st_vwap_cross_recent": bool(record.get("st_vwap_cross_recent")),
            "st_vwap_cross_new": bool(record.get("st_vwap_cross_new")),
            "workflow_state": record.get("candidate_status") or record.get("status"),
        },
    }


def install() -> None:
    """Short-circuit GS421 before dataframe/ST work for ordinary analyzed records."""
    current = gs421.build_maturation_evidence
    if getattr(current, "_gs422_selective_maturation", False):
        return

    @wraps(current)
    def selective_build(record: dict, raw_rows, client) -> dict:
        if not should_record_maturation(record):
            return skipped_evidence(record)
        return current(record, raw_rows, client)

    selective_build._gs422_selective_maturation = True
    selective_build._gs422_original = current
    gs421.build_maturation_evidence = selective_build

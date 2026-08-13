"""Deterministic replay primitives for Walter decision-time evidence.

Replay is intentionally read-only: it explains a recorded decision from the
immutable evidence captured at decision time.  It does not fetch market data,
re-run discovery, or alter scoring/trading policy.
"""

from __future__ import annotations

from copy import deepcopy

from mide.decision_time_evidence import verify_decision_time_evidence


class InvalidDecisionEvidence(ValueError):
    """Raised when replay is attempted with mutated or incomplete evidence."""


def replay_decision(evidence: dict) -> dict:
    """Return a deterministic explanation of the decision frozen in evidence."""
    if not verify_decision_time_evidence(evidence):
        raise InvalidDecisionEvidence("decision-time evidence failed integrity verification")

    e = deepcopy(evidence)
    participation = e.get("participation_gate") or {}
    structure = e.get("structure_gate") or {}
    trigger = e.get("trigger_diagnostics") or {}

    blockers = list(e.get("entry_blockers_explained") or [])
    if e.get("rejection_reason") and e["rejection_reason"] not in blockers:
        blockers.insert(0, e["rejection_reason"])
    for check in trigger.get("checks", []):
        if not check.get("passed"):
            reason = check.get("failed_reason") or check.get("condition")
            if reason and reason not in blockers:
                blockers.append(reason)

    if not participation.get("passed", False):
        replay_state = "PARTICIPATION_BLOCKED"
    elif not structure.get("passed", False):
        replay_state = "STRUCTURE_BLOCKED"
    elif e.get("qualified_for_entry"):
        replay_state = "ENTRY_READY"
    elif e.get("qualified_for_watch"):
        replay_state = "WATCH"
    else:
        replay_state = "OBSERVE"

    return {
        "scan_id": e.get("scan_id"),
        "scan_timestamp": e.get("scan_timestamp"),
        "symbol": e.get("symbol"),
        "evidence_sha256": e.get("evidence_sha256"),
        "integrity_verified": True,
        "replay_state": replay_state,
        "recorded_status": e.get("candidate_status") or e.get("status"),
        "qualified_for_watch": bool(e.get("qualified_for_watch")),
        "qualified_for_entry": bool(e.get("qualified_for_entry")),
        "qualified_for_alert": bool(e.get("qualified_for_alert")),
        "trigger_result": e.get("trigger_result"),
        "blockers": blockers,
        "source_bar_timestamp": e.get("source_bar_timestamp"),
        "source_bar_age_seconds": e.get("source_bar_age_seconds"),
        "decision_inputs": {
            "price": e.get("price"),
            "vwap_value": e.get("vwap_value"),
            "vwap_distance_pct": e.get("vwap_distance_pct"),
            "volume_pace_ratio": e.get("volume_pace_ratio"),
            "acceleration_ratio": e.get("acceleration_ratio"),
            "supertrend_state": e.get("supertrend_state"),
            "timeframe_alignment": e.get("timeframe_alignment"),
            "quality_score": e.get("quality_score"),
            "opportunity_score": e.get("opportunity_score"),
            "conviction_score": e.get("conviction_score"),
        },
    }

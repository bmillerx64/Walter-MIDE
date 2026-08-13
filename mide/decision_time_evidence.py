"""Immutable decision-time evidence snapshots for Walter.

This module deliberately contains no scoring or trading policy.  It captures the
facts Walter had when a scan decision was made so later replay cannot silently
substitute newer market data.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json

EVIDENCE_SCHEMA_VERSION = 1


def _utc_iso(value: datetime | str | None) -> str:
    if isinstance(value, str) and value:
        return value
    value = value or datetime.now(timezone.utc)
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()


def _canonical_payload(payload: dict) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def evidence_digest(payload: dict) -> str:
    """Return a stable digest proving exactly which evidence was recorded."""
    return hashlib.sha256(_canonical_payload(payload).encode("utf-8")).hexdigest()


def capture_decision_time_evidence(
    record: dict | None,
    *,
    scan_id: str,
    scan_timestamp: datetime | str | None,
    data_mode: str | None = None,
) -> dict:
    """Freeze the decision-relevant fields present at scan publication time."""
    record = record or {}
    trigger = deepcopy(record.get("trigger_diagnostics") or {})
    participation = deepcopy(record.get("participation_gate") or {})
    structure = deepcopy(record.get("structure_gate") or {})
    evidence = {
        "schema_version": EVIDENCE_SCHEMA_VERSION,
        "scan_id": scan_id,
        "scan_timestamp": _utc_iso(scan_timestamp),
        "symbol": str(record.get("symbol") or "").upper(),
        "data_mode": data_mode,
        "source_bar_timestamp": record.get("source_bar_timestamp")
        or record.get("last_bar_timestamp")
        or record.get("bar_timestamp"),
        "source_bar_age_seconds": record.get("source_bar_age")
        or record.get("bar_age_seconds"),
        "price": record.get("price"),
        "pct_change": record.get("pct_change"),
        "volume": record.get("volume"),
        "dollar_volume": record.get("dollar_volume"),
        "spread_pct": record.get("spread_pct"),
        "vwap_value": record.get("vwap_value"),
        "vwap_distance_pct": record.get("vwap_distance_pct"),
        "volume_pace_ratio": record.get("volume_pace_ratio"),
        "acceleration_ratio": record.get("acceleration_ratio"),
        "volume_acceleration": record.get("volume_acceleration"),
        "dollar_flow_acceleration": record.get(
            "dollar_flow_acceleration_5m", record.get("dollar_flow_acceleration")
        ),
        "supertrend_state": record.get("supertrend_state"),
        "supertrend_bullish": record.get("supertrend_bullish"),
        "supertrend_flip_age_seconds": record.get(
            "supertrend_30s_flip_age_seconds",
            record.get("supertrend_flip_age_seconds", record.get("supertrend_flip_age")),
        ),
        "timeframes": deepcopy(record.get("timeframes") or {}),
        "timeframe_alignment": deepcopy(record.get("timeframe_alignment") or {}),
        "alignment_score": record.get("alignment_score"),
        "alignment_total": record.get("alignment_total"),
        "alignment_label": record.get("alignment_label"),
        "participation_gate": participation,
        "structure_gate": structure,
        "trigger_diagnostics": trigger,
        "trigger_result": trigger.get("trigger", record.get("trigger")),
        "quality_score": record.get("quality_score"),
        "quality_grade": record.get("quality_grade"),
        "quality_score_breakdown": deepcopy(record.get("quality_score_breakdown")),
        "opportunity_score": record.get("opportunity_score"),
        "conviction_score": record.get("conviction_v2_score", record.get("conviction_score")),
        "candidate_status": record.get("candidate_status"),
        "status": record.get("status"),
        "qualified_for_ranking": record.get("qualified_for_ranking"),
        "qualified_for_watch": record.get("qualified_for_watch"),
        "qualified_for_entry": record.get("qualified_for_entry"),
        "qualified_for_alert": record.get("qualified_for_alert"),
        "rejection_reason": record.get("rejection_reason"),
        "entry_blockers_explained": deepcopy(record.get("entry_blockers_explained") or []),
    }
    frozen = deepcopy(evidence)
    frozen["evidence_sha256"] = evidence_digest(evidence)
    return frozen


def verify_decision_time_evidence(evidence: dict) -> bool:
    """Detect accidental or retrospective mutation of a recorded evidence snapshot."""
    evidence = deepcopy(evidence or {})
    recorded = evidence.pop("evidence_sha256", None)
    return bool(recorded and recorded == evidence_digest(evidence))

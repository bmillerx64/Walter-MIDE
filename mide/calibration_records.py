"""Immutable calibration records built from verified decision evidence and outcomes.

This module is deliberately downstream from Walter's live decision path.  It may
join a historical decision-time evidence snapshot to a strictly-forward outcome,
but it never changes discovery, scoring, qualification, ranking, alerts, or entry
state.
"""

from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from statistics import mean, median
from typing import Any, Iterable, Mapping

from mide.decision_time_evidence import verify_decision_time_evidence


CALIBRATION_SCHEMA_VERSION = 1


class InvalidCalibrationRecord(ValueError):
    """Raised when evidence/outcome lineage is incomplete or inconsistent."""


def _canonical_payload(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def calibration_digest(payload: Mapping[str, Any]) -> str:
    """Return a stable digest for one calibration record payload."""
    return hashlib.sha256(_canonical_payload(payload).encode("utf-8")).hexdigest()


def _number(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _decision_features(evidence: Mapping[str, Any]) -> dict[str, Any]:
    """Copy decision-time predictors without introducing retrospective fields."""
    scalar_keys = (
        "price", "pct_change", "volume", "dollar_volume", "spread_pct",
        "vwap_value", "vwap_distance_pct", "volume_pace_ratio",
        "acceleration_ratio", "volume_acceleration", "dollar_flow_acceleration",
        "supertrend_state", "supertrend_bullish", "supertrend_flip_age_seconds",
        "alignment_score", "alignment_total", "alignment_label", "trigger_result",
        "quality_score", "quality_grade", "opportunity_score", "conviction_score",
        "candidate_status", "status", "qualified_for_ranking",
        "qualified_for_watch", "qualified_for_entry", "qualified_for_alert",
        "rejection_reason",
    )
    nested_keys = (
        "timeframes", "timeframe_alignment", "participation_gate", "structure_gate",
        "trigger_diagnostics", "quality_score_breakdown", "entry_blockers_explained",
    )
    features = {key: deepcopy(evidence.get(key)) for key in scalar_keys}
    features.update({key: deepcopy(evidence.get(key)) for key in nested_keys})
    return features


def build_calibration_record(evidence: dict, outcome: dict) -> dict:
    """Join one immutable decision snapshot to one strictly-forward outcome label.

    The lineage checks make it impossible to silently attach an outcome to a
    different scan, symbol, decision timestamp, or evidence digest.
    """
    evidence = deepcopy(evidence or {})
    outcome = deepcopy(outcome or {})

    if not verify_decision_time_evidence(evidence):
        raise InvalidCalibrationRecord("decision-time evidence failed integrity verification")

    expected_sha = evidence.get("evidence_sha256")
    lineage = {
        "scan_id": (evidence.get("scan_id"), outcome.get("scan_id")),
        "symbol": (evidence.get("symbol"), outcome.get("symbol")),
        "decision_timestamp": (
            evidence.get("scan_timestamp"), outcome.get("decision_timestamp")
        ),
        "evidence_sha256": (expected_sha, outcome.get("evidence_sha256")),
    }
    mismatches = [name for name, pair in lineage.items() if pair[0] != pair[1]]
    if mismatches:
        raise InvalidCalibrationRecord(
            "outcome lineage mismatch: " + ", ".join(sorted(mismatches))
        )

    horizon = outcome.get("horizon_minutes")
    try:
        horizon = int(horizon)
    except (TypeError, ValueError) as exc:
        raise InvalidCalibrationRecord("outcome horizon_minutes is invalid") from exc
    if horizon <= 0:
        raise InvalidCalibrationRecord("outcome horizon_minutes must be positive")

    required_metrics = ("mfe_pct", "mae_pct", "end_return_pct", "time_to_mfe_seconds")
    metrics = {key: _number(outcome.get(key)) for key in required_metrics}
    if any(value is None for value in metrics.values()):
        raise InvalidCalibrationRecord("outcome metrics are incomplete")

    payload = {
        "schema_version": CALIBRATION_SCHEMA_VERSION,
        "scan_id": evidence.get("scan_id"),
        "symbol": evidence.get("symbol"),
        "decision_timestamp": evidence.get("scan_timestamp"),
        "evidence_sha256": expected_sha,
        "horizon_minutes": horizon,
        "decision_features": _decision_features(evidence),
        "outcome": {
            **metrics,
            "bars_observed": int(outcome.get("bars_observed") or 0),
            "entry_price": _number(outcome.get("entry_price")),
            "max_forward_high": _number(outcome.get("max_forward_high")),
            "min_forward_low": _number(outcome.get("min_forward_low")),
            "outcome_source": outcome.get("outcome_source"),
        },
    }
    record = deepcopy(payload)
    record["calibration_sha256"] = calibration_digest(payload)
    return record


def verify_calibration_record(record: Mapping[str, Any]) -> bool:
    """Detect accidental or retrospective mutation of a calibration record."""
    payload = deepcopy(dict(record or {}))
    recorded = payload.pop("calibration_sha256", None)
    return bool(recorded and recorded == calibration_digest(payload))


def _average(values: Iterable[float]) -> float | None:
    numbers = list(values)
    return mean(numbers) if numbers else None


def _median(values: Iterable[float]) -> float | None:
    numbers = list(values)
    return median(numbers) if numbers else None


def aggregate_calibration_records(records: Iterable[Mapping[str, Any]]) -> dict:
    """Aggregate verified calibration records by fixed forward horizon.

    Invalid or mutated records are rejected rather than silently included.  The
    summary is descriptive only and has no runtime policy authority.
    """
    verified = []
    for source in records or []:
        record = deepcopy(dict(source))
        if not verify_calibration_record(record):
            raise InvalidCalibrationRecord("calibration record failed integrity verification")
        verified.append(record)

    groups: dict[int, list[dict]] = {}
    for record in verified:
        horizon = int(record["horizon_minutes"])
        groups.setdefault(horizon, []).append(record)

    horizons = {}
    for horizon in sorted(groups):
        group = groups[horizon]
        mfe = [float(item["outcome"]["mfe_pct"]) for item in group]
        mae = [float(item["outcome"]["mae_pct"]) for item in group]
        ending = [float(item["outcome"]["end_return_pct"]) for item in group]
        time_to_mfe = [float(item["outcome"]["time_to_mfe_seconds"]) for item in group]
        positive = sum(value > 0 for value in ending)
        horizons[str(horizon)] = {
            "horizon_minutes": horizon,
            "observations": len(group),
            "average_mfe_pct": _average(mfe),
            "median_mfe_pct": _median(mfe),
            "average_mae_pct": _average(mae),
            "median_mae_pct": _median(mae),
            "average_end_return_pct": _average(ending),
            "median_end_return_pct": _median(ending),
            "positive_end_return_rate_pct": (positive / len(group)) * 100.0,
            "average_time_to_mfe_seconds": _average(time_to_mfe),
        }

    return {
        "schema_version": CALIBRATION_SCHEMA_VERSION,
        "observations": len(verified),
        "horizons": horizons,
        "policy_authority": "none; descriptive downstream calibration only",
    }

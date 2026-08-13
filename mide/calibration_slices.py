"""Descriptive calibration slices for immutable Walter calibration records.

This module is downstream analytics only. It has no authority over live discovery,
scoring, qualification, ranking, alerts, thresholds, or entry state.
"""

from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
from statistics import mean, median
from typing import Any, Iterable, Mapping

from mide.calibration_records import InvalidCalibrationRecord, verify_calibration_record


def _bucket(value: Any, edges: tuple[float, ...]) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "unknown"
    previous = None
    for edge in edges:
        if number < edge:
            return f"<{edge:g}" if previous is None else f"{previous:g}-{edge:g}"
        previous = edge
    return f">={edges[-1]:g}"


def _slice_value(record: Mapping[str, Any], dimension: str) -> str:
    features = record.get("decision_features") or {}
    if dimension == "candidate_status":
        return str(features.get("candidate_status") or features.get("status") or "unknown")
    if dimension == "quality_grade":
        return str(features.get("quality_grade") or "unknown")
    if dimension == "alignment_label":
        return str(features.get("alignment_label") or "unknown")
    if dimension == "trigger_result":
        value = features.get("trigger_result")
        return "unknown" if value is None else str(value)
    if dimension == "qualified_for_entry":
        value = features.get("qualified_for_entry")
        return "unknown" if value is None else str(bool(value))
    if dimension == "quality_score":
        return _bucket(features.get("quality_score"), (40, 60, 75, 90))
    if dimension == "conviction_score":
        return _bucket(features.get("conviction_score"), (40, 60, 75, 90))
    if dimension == "vwap_distance_pct":
        return _bucket(features.get("vwap_distance_pct"), (-5, 0, 2, 5, 10))
    if dimension == "volume_pace_ratio":
        return _bucket(features.get("volume_pace_ratio"), (1, 2, 5, 10))
    raise ValueError(f"unsupported calibration dimension: {dimension}")


def _summary(group: list[Mapping[str, Any]]) -> dict:
    mfe = [float(item["outcome"]["mfe_pct"]) for item in group]
    mae = [float(item["outcome"]["mae_pct"]) for item in group]
    ending = [float(item["outcome"]["end_return_pct"]) for item in group]
    time_to_mfe = [float(item["outcome"]["time_to_mfe_seconds"]) for item in group]
    return {
        "observations": len(group),
        "average_mfe_pct": mean(mfe),
        "median_mfe_pct": median(mfe),
        "average_mae_pct": mean(mae),
        "median_mae_pct": median(mae),
        "average_end_return_pct": mean(ending),
        "median_end_return_pct": median(ending),
        "positive_end_return_rate_pct": (sum(value > 0 for value in ending) / len(group)) * 100.0,
        "average_time_to_mfe_seconds": mean(time_to_mfe),
    }


def slice_calibration_records(
    records: Iterable[Mapping[str, Any]], *, dimension: str, min_observations: int = 1
) -> dict:
    """Compare verified fixed-horizon outcomes across one decision-time dimension."""
    if min_observations <= 0:
        raise ValueError("min_observations must be positive")

    groups: dict[tuple[int, str], list[Mapping[str, Any]]] = defaultdict(list)
    verified_count = 0
    for source in records or []:
        record = deepcopy(dict(source))
        if not verify_calibration_record(record):
            raise InvalidCalibrationRecord("calibration record failed integrity verification")
        verified_count += 1
        horizon = int(record["horizon_minutes"])
        groups[(horizon, _slice_value(record, dimension))].append(record)

    horizons: dict[str, dict] = {}
    for (horizon, label), group in sorted(groups.items(), key=lambda item: (item[0][0], item[0][1])):
        horizon_result = horizons.setdefault(str(horizon), {"horizon_minutes": horizon, "slices": {}})
        if len(group) >= min_observations:
            horizon_result["slices"][label] = _summary(group)

    return {
        "dimension": dimension,
        "observations": verified_count,
        "min_observations": min_observations,
        "horizons": horizons,
        "policy_authority": "none; descriptive downstream calibration only",
    }

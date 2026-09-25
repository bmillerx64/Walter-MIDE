"""GS554: observational Participation latency decomposition.

Post-transition CAB evidence showed Participation Assessment consuming roughly
29-35 seconds while recorded Stage-6 provider history I/O was only about 1-4
seconds. GS554 measures the existing Participation sub-phases without changing
their order, inputs, outputs, thresholds, provider calls, or trading authority.

A unique hot-deploy installer augments GS425 latency truth so the breakdown is
persisted into Flight Recorder/CAB evidence even when a warm runtime retains an
older GS425 module generation.
"""
from __future__ import annotations

from copy import deepcopy
from functools import wraps
from typing import Any


AUTHORITY = "OBSERVATIONAL_ONLY"
DIAGNOSTIC_KEY = "gs554_participation_latency_breakdown"
_OWNER = "_gs554_participation_latency_breakdown"


def _milliseconds(value: Any) -> float:
    try:
        return round(max(0.0, float(value)), 3)
    except (TypeError, ValueError):
        return 0.0


def record_breakdown(
    provider,
    *,
    stage_input_count: int,
    prefilter_output_count: int,
    history_symbol_count: int,
    analyzed_count: int,
    pre_analysis_ms: float,
    analyze_candidates_ms: float,
    velocity_enrichment_ms: float,
    scanner_v2_ms: float,
    decision_materialization_ms: float,
    total_ms: float,
) -> dict[str, Any]:
    """Attach one successful-scan Participation timing snapshot to diagnostics."""
    payload = {
        "authority": AUTHORITY,
        "purpose": "locate Participation latency without changing scan behavior",
        "stage_input_count": int(stage_input_count),
        "prefilter_output_count": int(prefilter_output_count),
        "history_symbol_count": int(history_symbol_count),
        "analyzed_count": int(analyzed_count),
        "pre_analysis_ms": _milliseconds(pre_analysis_ms),
        "analyze_candidates_ms": _milliseconds(analyze_candidates_ms),
        "velocity_enrichment_ms": _milliseconds(velocity_enrichment_ms),
        "scanner_v2_ms": _milliseconds(scanner_v2_ms),
        "decision_materialization_ms": _milliseconds(decision_materialization_ms),
        "total_ms": _milliseconds(total_ms),
        "extra_provider_calls": 0,
        "market_data_values_changed": False,
        "trading_logic_changed": False,
    }
    diagnostics = getattr(provider, "diagnostics", None)
    if isinstance(diagnostics, dict):
        hotspots = diagnostics.get("gs557_analyze_candidates_hotspots")
        if isinstance(hotspots, dict):
            payload["analyze_candidates_hotspots"] = deepcopy(hotspots)
        diagnostics[DIAGNOSTIC_KEY] = deepcopy(payload)
    return payload


def augment_latency_truth(provider, truth: dict | None) -> dict:
    """Persist GS554 diagnostics beside existing GS425 provider-latency truth."""
    result = deepcopy(dict(truth or {}))
    diagnostics = getattr(provider, "diagnostics", None)
    breakdown = (
        deepcopy(diagnostics.get(DIAGNOSTIC_KEY) or {})
        if isinstance(diagnostics, dict)
        else {}
    )
    if not breakdown:
        return result

    try:
        history_ms = float(result.get("stage6_history_elapsed_ms") or 0.0)
    except (TypeError, ValueError):
        history_ms = 0.0
    try:
        analyze_ms = float(breakdown.get("analyze_candidates_ms") or 0.0)
    except (TypeError, ValueError):
        analyze_ms = 0.0

    breakdown["stage6_history_elapsed_ms"] = round(max(0.0, history_ms), 3)
    breakdown["analyze_candidates_non_history_ms"] = round(
        max(0.0, analyze_ms - history_ms),
        3,
    )
    result["participation_latency_breakdown"] = breakdown
    return result


def install() -> bool:
    """Warm-deploy-safe hard bind at GS425's persisted latency-truth seam."""
    from mide import gs425_latency_truth_recorder as gs425

    current = gs425.build_latency_truth
    if getattr(current, _OWNER, False):
        return False

    @wraps(current)
    def build_latency_truth(provider, events=None):
        return augment_latency_truth(
            provider,
            current(provider, events),
        )

    setattr(build_latency_truth, _OWNER, True)
    build_latency_truth._gs554_original = current
    gs425.build_latency_truth = build_latency_truth
    return True


__all__ = [
    "AUTHORITY",
    "DIAGNOSTIC_KEY",
    "record_breakdown",
    "augment_latency_truth",
    "install",
]

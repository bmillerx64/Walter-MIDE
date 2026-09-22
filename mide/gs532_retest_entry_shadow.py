"""GS532: shadow a distinct 3m-retest/recovery Entry Ready lane.

Walter's canonical ignition trigger requires a recent ST flip. That is appropriate for
fresh ignition, but a different setup class exists after a held 3m SuperTrend retest:
thesis held -> VWAP acceptance -> 30s/1m repair. GS514/515 already reconstruct and
present that sequence, but it has no entry authority.

GS532 measures that setup as an observational counterfactual only. It does not change
qualified_for_entry, readiness, ranking, anti-chase, alerts, execution, or orders.
"""
from __future__ import annotations

from .gs514_retest_event_memory import discipline_sequence

VWAP_MIN_PCT = -0.75
VWAP_MAX_PCT = 2.0
MIN_PARTICIPATION = 60.0
MIN_EXPANSION = 55.0


def retest_entry_shadow(record: dict) -> dict:
    maturation = record.get("multitimeframe_maturation") or {}
    event = maturation.get("three_minute_st_retest_event") or {}
    seq = discipline_sequence(record, event) if isinstance(event, dict) else {}
    distance = float(record.get("vwap_distance_pct") or 0.0)
    participation = float(
        (record.get("participation_surge_diagnostics") or {}).get(
            "participation_score", record.get("participation_surge_score") or 0.0
        ) or 0.0
    )
    expansion = float(record.get("expansion_quality") or 0.0)

    checks = {
        "three_minute_retest_held": bool(event.get("active_memory")),
        "lower_timeframe_repair_complete": bool(seq.get("lower_timeframe_repair_complete")),
        "vwap_entry_window": VWAP_MIN_PCT <= distance <= VWAP_MAX_PCT,
        "participation": participation >= MIN_PARTICIPATION,
        "expansion": expansion >= MIN_EXPANSION,
    }
    failed = [name for name, passed in checks.items() if not passed]
    return {
        "authority": "OBSERVATIONAL_ONLY",
        "shadow_entry_ready": not failed,
        "checks": checks,
        "failed_conditions": failed,
        "three_minute_retest_event": dict(event) if isinstance(event, dict) else {},
        "discipline_sequence": seq,
        "vwap_distance_pct": round(distance, 3),
        "participation_score": round(participation, 1),
        "expansion_quality": round(expansion, 1),
        "thresholds": {
            "vwap_min_pct": VWAP_MIN_PCT,
            "vwap_max_pct": VWAP_MAX_PCT,
            "participation_min": MIN_PARTICIPATION,
            "expansion_min": MIN_EXPANSION,
        },
        "trading_authority_changed": False,
    }

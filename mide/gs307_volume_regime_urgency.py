"""GS307: identify fresh volume-regime changes for human review only.

This module is intentionally presentation/alert intelligence. It does not change
scanner discovery, stage decisions, scores, rankings, readiness, triggers, or
execution. It answers one narrow question: did a continuously watched symbol with
already-supportive structure just transition from ordinary participation into a
meaningfully hotter tape?
"""
from __future__ import annotations


def _number(record: dict, *keys: str) -> float | None:
    for key in keys:
        value = record.get(key)
        if value is None:
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return None


def _tf(record: dict, label: str) -> dict:
    return (record.get("timeframes") or {}).get(label) or {}


def volume_regime_urgency(record: dict) -> dict:
    """Detect a fresh quiet→active tape transition on established bullish structure.

    Unlike first-print ignition, a new SuperTrend flip is not required here. The
    intended case is MGN-like: Walter already knows the symbol, price has been
    holding above VWAP with bullish trend support, and then 1m/3m participation
    suddenly accelerates relative to the immediately prior scan.
    """
    previous = record.get("opportunity_pulse_previous") or {}
    continuity = bool(previous)
    reevaluation_status = str(record.get("reevaluation_status") or "").upper()
    fresh_observation = reevaluation_status != "NOT_IN_CURRENT_REFRESH"

    state = str(record.get("candidate_status") or record.get("status") or "")
    watch_eligible = state not in {"Removed", "Rejected – No Participation", "Rejected"}

    relation = str(record.get("vwap_relation") or "").lower()
    vwap_supported = bool(
        relation == "above"
        or _tf(record, "1m").get("above_vwap")
        or _tf(record, "3m").get("above_vwap")
    )
    trend_supported = bool(
        record.get("supertrend_bullish")
        or _tf(record, "1m").get("supertrend")
        or _tf(record, "3m").get("supertrend")
    )

    current_1m = _number(record, "volume_acceleration_1m", "volume_acceleration") or 1.0
    current_3m = _number(record, "volume_acceleration_3m", "volume_acceleration") or 1.0
    prior_1m = _number(previous, "volume_acceleration_1m", "volume_acceleration") or 1.0
    prior_3m = _number(previous, "volume_acceleration_3m", "volume_acceleration") or 1.0

    one_minute_jump = bool(current_1m >= 2.0 and current_1m >= max(1.0, prior_1m) * 1.5)
    three_minute_jump = bool(current_3m >= 1.6 and current_3m >= max(1.0, prior_3m) * 1.35)
    fresh_volume_regime = one_minute_jump or three_minute_jump

    dollar_1m = _number(record, "dollar_flow_acceleration_1m")
    dollar_3m = _number(record, "dollar_flow_acceleration_3m")
    dollar_confirmation = max(
        value for value in (dollar_1m or 0.0, dollar_3m or 0.0)
    ) >= 1.5

    surge = record.get("participation_surge_diagnostics") or {}
    participation = _number(
        record, "participation_surge_score", "participation_score"
    )
    if participation is None:
        participation = _number(surge, "participation_score") or 0.0
    rvol = _number(record, "rvol_proxy", "rvol") or 0.0
    participation_confirmation = bool(
        dollar_confirmation or participation >= 60.0 or rvol >= 1.5
    )

    promoted = bool(
        continuity
        and fresh_observation
        and watch_eligible
        and vwap_supported
        and trend_supported
        and fresh_volume_regime
        and participation_confirmation
    )

    return {
        "promoted": promoted,
        "continuity": continuity,
        "fresh_observation": fresh_observation,
        "watch_eligible": watch_eligible,
        "vwap_supported": vwap_supported,
        "trend_supported": trend_supported,
        "fresh_volume_regime": fresh_volume_regime,
        "one_minute_jump": one_minute_jump,
        "three_minute_jump": three_minute_jump,
        "volume_acceleration_1m": round(current_1m, 2),
        "volume_acceleration_3m": round(current_3m, 2),
        "prior_volume_acceleration_1m": round(prior_1m, 2),
        "prior_volume_acceleration_3m": round(prior_3m, 2),
        "participation_confirmation": participation_confirmation,
        "participation_score": round(float(participation), 1),
        "rvol": round(rvol, 2),
        "dollar_flow_confirmed": dollar_confirmation,
    }

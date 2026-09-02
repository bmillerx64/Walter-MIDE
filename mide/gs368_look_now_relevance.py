"""GS368: tighten top-mover-only LOOK NOW relevance without changing trading logic.

Live validation on 2026-09-02 showed the GS367 browser broker correctly emitting a
two-tone LOOK NOW cadence for GELS after the close, but the underlying opportunity
state was too permissive.  GELS was near VWAP with bullish SuperTrend and modest
participation, so GS364's top-mover fallback allowed LOOK NOW even though no fresh
volume or dollar-flow confirmation was present.

This presentation/attention layer preserves the scanner, discovery membership,
scoring, ranking, qualification, readiness thresholds, execution, and orders.  It
only tightens the special WEBULL_TOP_MOVER-only path to LOOK NOW:

* price must be above and within 2% of VWAP;
* SuperTrend must be bullish;
* participation must be at least 30; and
* at least one fresh dynamic-flow cue must be present: volume acceleration >= 1.0x
  or dollar-flow acceleration >= 1.25x.

Fresh news, second-wave re-ignition, and fresh volume-regime attention keep their
established early LOOK NOW behavior.  The VIOT-like live pattern captured by GS364
also remains LOOK NOW because it had participation 31.6 and dollar-flow
acceleration 1.74 while still below the later entry thresholds.
"""
from __future__ import annotations

from copy import deepcopy


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


def calibrated_opportunity_state(record: dict) -> dict:
    """Downgrade weak top-mover-only LOOK NOW states to DEVELOPING."""
    from . import gs310_unified_opportunity_state as unified

    original = getattr(
        unified.opportunity_state,
        "_gs368_original",
        unified.opportunity_state,
    )
    view = original(record)
    if view.get("state") != unified.LOOK_NOW:
        return view

    provenance = set(view.get("attention_provenance") or [])
    if provenance.intersection(
        {"FRESH_NEWS_SEED", "FRESH_REIGNITION", "FRESH_VOLUME_REGIME"}
    ):
        return view
    if "WEBULL_TOP_MOVER" not in provenance:
        return view

    relation = str(record.get("vwap_relation") or "").lower()
    distance = _number(record, "vwap_distance_pct")
    near_vwap = relation == "above" and (
        distance is None or 0.0 <= distance <= 2.0
    )
    trend = bool(record.get("supertrend_bullish") or record.get("supertrend_flip"))
    participation = (
        _number(record, "participation_surge_score", "participation_score") or 0.0
    )
    volume_acceleration = _number(record, "volume_acceleration") or 0.0
    dollar_flow = _number(record, "dollar_flow_acceleration") or 0.0

    fresh_flow = volume_acceleration >= 1.0 or dollar_flow >= 1.25
    participation_support = participation >= 30.0

    if near_vwap and trend and participation_support and fresh_flow:
        return view

    downgraded = deepcopy(view)
    downgraded["state"] = unified.DEVELOPING
    downgraded["color"] = unified.STATE_COLORS[unified.DEVELOPING]
    downgraded["reason"] = (
        "Top-mover attention is present, but LOOK NOW needs current participation "
        "plus fresh volume or dollar-flow confirmation."
    )
    downgraded["next_step"] = (
        "Keep monitoring until price/trend, participation, and fresh flow align."
    )
    return downgraded


def _inherit(wrapper, wrapped) -> None:
    for name, value in getattr(wrapped, "__dict__", {}).items():
        if name.startswith("_gs") and not hasattr(wrapper, name):
            setattr(wrapper, name, value)


def install() -> None:
    """Install GS368 consistently across every trader-facing state binding."""
    from . import gs310_unified_opportunity_state as unified
    from . import gs311_unified_voice as voice
    from . import gs314_state_consistency as consistency
    from . import gs363_operator_attention_hierarchy as hierarchy

    current = unified.opportunity_state
    if getattr(current, "_gs368_look_now_relevance", False):
        calibrated = current
    else:
        original = current

        def calibrated(record: dict) -> dict:
            view = original(record)
            if view.get("state") != unified.LOOK_NOW:
                return view

            provenance = set(view.get("attention_provenance") or [])
            if provenance.intersection(
                {"FRESH_NEWS_SEED", "FRESH_REIGNITION", "FRESH_VOLUME_REGIME"}
            ):
                return view
            if "WEBULL_TOP_MOVER" not in provenance:
                return view

            relation = str(record.get("vwap_relation") or "").lower()
            distance = _number(record, "vwap_distance_pct")
            near_vwap = relation == "above" and (
                distance is None or 0.0 <= distance <= 2.0
            )
            trend = bool(
                record.get("supertrend_bullish") or record.get("supertrend_flip")
            )
            participation = (
                _number(record, "participation_surge_score", "participation_score")
                or 0.0
            )
            volume_acceleration = _number(record, "volume_acceleration") or 0.0
            dollar_flow = _number(record, "dollar_flow_acceleration") or 0.0

            fresh_flow = volume_acceleration >= 1.0 or dollar_flow >= 1.25
            participation_support = participation >= 30.0
            if near_vwap and trend and participation_support and fresh_flow:
                return view

            downgraded = deepcopy(view)
            downgraded["state"] = unified.DEVELOPING
            downgraded["color"] = unified.STATE_COLORS[unified.DEVELOPING]
            downgraded["reason"] = (
                "Top-mover attention is present, but LOOK NOW needs current "
                "participation plus fresh volume or dollar-flow confirmation."
            )
            downgraded["next_step"] = (
                "Keep monitoring until price/trend, participation, and fresh flow align."
            )
            return downgraded

        _inherit(calibrated, current)
        calibrated._gs368_look_now_relevance = True
        calibrated._gs368_original = original
        unified.opportunity_state = calibrated

    voice.opportunity_state = calibrated
    consistency.opportunity_state = calibrated
    hierarchy.opportunity_state = calibrated

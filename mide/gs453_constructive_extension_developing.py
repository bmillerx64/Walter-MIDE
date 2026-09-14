"""GS453: classify bounded constructive extension as DEVELOPING, not CHASE / WAIT.

Live validation on VSME on 2026-09-14 exposed a presentation gap between GS310's
strict +2% VWAP chase label and GS394's much narrower consolidation-rearm LOOK NOW
path. VSME was only ~2.4% above VWAP with a constructive 30s -> 1m ladder and a
non-vertical tape, while participation/flow had faded and 3m confirmation still
needed renewed volume. Calling that geometry CHASE / WAIT overstated extension and
hid the useful operator truth: structure remained constructive, but momentum had not
yet earned a new escalation.

GS453 is display/attention semantics only. It does not alter VWAP/ST calculations,
discovery, ranking, participation/expansion scores, qualification, entry/readiness,
anti-chase trading locks, alert authority, execution, or orders.

A CHASE / WAIT view may become DEVELOPING only when:
* price is above VWAP by >2% and <=5%;
* the canonical 30s and 1m alignment members are both aligned;
* at least two of the canonical 30s/1m/3m members are aligned;
* 10-minute price change is not already vertical (<=6% absolute); and
* the record is not halted.

The visible guidance explicitly preserves the underlying anti-chase guard. Fresh flow
or later 3m confirmation may still allow existing GS394/GS404 paths to escalate the
symbol; GS453 itself never creates LOOK NOW or WATCH FOR ENTRY.
"""
from __future__ import annotations

from copy import deepcopy

MIN_VWAP_DISTANCE_PCT = 2.0
MAX_VWAP_DISTANCE_PCT = 5.0
MIN_ALIGNMENT_SCORE = 2
MAX_10M_PRICE_CHANGE_PCT = 6.0
PARTICIPATION_REARM_LEVEL = 40.0
MIN_VOLUME_ACCELERATION = 1.0
MIN_DOLLAR_FLOW_ACCELERATION = 1.25


def _number(record: dict, *keys: str, default: float | None = None) -> float | None:
    for key in keys:
        value = record.get(key)
        if value is None or value == "":
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return default


def _aligned(record: dict, timeframe: str) -> bool:
    details = record.get("timeframe_alignment") or {}
    item = details.get(timeframe) if isinstance(details, dict) else None
    if isinstance(item, dict):
        return bool(item.get("aligned"))
    return False


def constructive_extension_evidence(record: dict) -> dict:
    """Return display-only evidence for bounded, constructive VWAP extension."""
    relation = str(record.get("vwap_relation") or "").strip().lower()
    distance = _number(record, "vwap_distance_pct")
    bounded = bool(
        relation == "above"
        and distance is not None
        and MIN_VWAP_DISTANCE_PCT < distance <= MAX_VWAP_DISTANCE_PCT
    )

    score = int(_number(record, "alignment_score", default=0.0) or 0.0)
    thirty_aligned = _aligned(record, "30s")
    one_aligned = _aligned(record, "1m")
    three_aligned = _aligned(record, "3m")
    ladder_constructive = bool(
        score >= MIN_ALIGNMENT_SCORE and thirty_aligned and one_aligned
    )

    change_10m = abs(_number(record, "price_change_10m_pct", default=999.0) or 999.0)
    nonvertical = change_10m <= MAX_10M_PRICE_CHANGE_PCT

    participation = _number(
        record, "participation_surge_score", "participation_score", default=0.0
    ) or 0.0
    volume_accel = _number(record, "volume_acceleration", default=0.0) or 0.0
    dollar_flow = _number(
        record,
        "dollar_flow_acceleration",
        "dollar_flow_acceleration_1m",
        default=0.0,
    ) or 0.0
    fresh_flow = bool(
        volume_accel >= MIN_VOLUME_ACCELERATION
        or dollar_flow >= MIN_DOLLAR_FLOW_ACCELERATION
    )
    participation_ready = participation >= PARTICIPATION_REARM_LEVEL

    halted = bool(
        record.get("halted")
        or record.get("is_halted")
        or record.get("suspended")
        or record.get("is_suspended")
    )

    qualifies = bool(bounded and ladder_constructive and nonvertical and not halted)
    return {
        "qualifies": qualifies,
        "display_only": True,
        "entry_chase_guard_still_authoritative": True,
        "vwap_distance_pct": distance,
        "bounded_extension": bounded,
        "alignment_score": score,
        "thirty_second_aligned": thirty_aligned,
        "one_minute_aligned": one_aligned,
        "three_minute_aligned": three_aligned,
        "ladder_constructive": ladder_constructive,
        "price_change_10m_pct": change_10m,
        "nonvertical": nonvertical,
        "participation_score": participation,
        "participation_ready": participation_ready,
        "volume_acceleration": volume_accel,
        "dollar_flow_acceleration": dollar_flow,
        "fresh_flow": fresh_flow,
    }


def _state_with_constructive_extension(original, record: dict) -> dict:
    from . import gs310_unified_opportunity_state as unified

    base = original(record)
    if base.get("state") != unified.CHASE_WAIT:
        return base

    evidence = constructive_extension_evidence(record)
    if not evidence["qualifies"]:
        return base

    view = deepcopy(base)
    view["state"] = unified.DEVELOPING
    view["color"] = unified.STATE_COLORS[unified.DEVELOPING]

    if not evidence["fresh_flow"] or not evidence["participation_ready"]:
        reason = (
            "Bounded VWAP extension with constructive 30s → 1m structure; "
            "momentum has not re-armed yet."
        )
        next_step = (
            "Wait for fresh participation/volume and 3m confirmation. Do not chase; "
            "the underlying entry guard remains authoritative."
        )
    elif not evidence["three_minute_aligned"]:
        reason = (
            "Fresh flow is improving inside a bounded extension, but 3m confirmation "
            "is still developing."
        )
        next_step = (
            "Watch for 3m confirmation while 30s and 1m stay constructive. This is "
            "still observation, not entry permission."
        )
    else:
        reason = (
            "Multi-timeframe structure remains constructive inside a bounded VWAP "
            "extension."
        )
        next_step = (
            "Continue monitoring for an existing re-arm/entry path; do not treat the "
            "DEVELOPING label as permission to chase."
        )

    view["reason"] = reason
    view["next_step"] = next_step
    view["constructive_extension"] = evidence
    return view


def _inherit(wrapper, wrapped) -> None:
    for name, value in getattr(wrapped, "__dict__", {}).items():
        if name.startswith("_gs") and not hasattr(wrapper, name):
            setattr(wrapper, name, value)


def install() -> None:
    """Install after existing LOOK NOW/retest state semantics."""
    from . import gs310_unified_opportunity_state as unified
    from . import gs311_unified_voice as voice
    from . import gs314_state_consistency as consistency
    from . import gs363_operator_attention_hierarchy as hierarchy

    current = unified.opportunity_state
    if getattr(current, "_gs453_constructive_extension", False):
        calibrated = current
    else:
        original = current

        def calibrated(record: dict) -> dict:
            return _state_with_constructive_extension(original, record)

        _inherit(calibrated, current)
        calibrated._gs453_constructive_extension = True
        calibrated._gs453_original = original
        unified.opportunity_state = calibrated

    voice.opportunity_state = calibrated
    consistency.opportunity_state = calibrated
    hierarchy.opportunity_state = calibrated

"""GS495: make extreme LOOK NOW location semantics unmistakable.

Sep. 18 live SSM validation showed that a truthful structural LOOK NOW can still be
operator-misleading when rendered as a giant yellow EXTREME MOVER · LOOK NOW banner
several percent above VWAP. The state may correctly mean "open the chart", while the
operator can understandably read the visual emphasis as trade permission.

GS495 keeps the underlying Opportunity State and every GS465 truth rule intact. It
only refines the extreme-mover banner when:
* current structure independently earned LOOK NOW, and
* price is > Walter's established 2% fresh-ignition location band, but
* price is not yet beyond the existing >5% DO NOT CHASE threshold.

That middle zone renders:
    EXTREME MOVER · LOOK NOW · WATCH RESET

The guidance says the structure earned attention, but the location is no longer fresh
enough to interpret LOOK NOW as entry permission. Above 5%, the existing DO NOT CHASE
language remains authoritative.

Presentation only. No discovery, market data, indicator formula, score, ranking,
qualification, readiness, anti-chase threshold, alert, execution or order change.
"""
from __future__ import annotations

from functools import wraps
from typing import Any, Callable

from .gs393_ignition_truth_extreme_decay import IGNITION_MAX_VWAP_DISTANCE_PCT

_OWNER = "_walter_gs495_extreme_look_now_reset_language"
DO_NOT_CHASE_DISTANCE_PCT = 5.0


def _number(value: Any) -> float | None:
    try:
        return float(value) if value is not None and value != "" else None
    except (TypeError, ValueError):
        return None


def refine_extreme_event(original: Callable, record: dict) -> dict | None:
    event = original(record)
    if not isinstance(event, dict):
        return event

    label = str(event.get("label") or "")
    upper = label.upper()
    if "HALTED" in upper or "DO NOT CHASE" in upper or "LOOK NOW" not in upper:
        return event

    distance = _number(event.get("vwap_distance_pct"))
    if distance is None:
        distance = _number(record.get("vwap_distance_pct"))
    if (
        distance is None
        or distance <= IGNITION_MAX_VWAP_DISTANCE_PCT
        or distance > DO_NOT_CHASE_DISTANCE_PCT
    ):
        return event

    refined = dict(event)
    refined["label"] = "EXTREME MOVER · LOOK NOW · WATCH RESET"
    refined["guidance"] = (
        "Current structure independently earned LOOK NOW, but price is "
        f"{distance:.1f}% above VWAP — outside Walter's existing "
        f"{IGNITION_MAX_VWAP_DISTANCE_PCT:.0f}% fresh-ignition location band. "
        "Keep the chart open and watch for a reset/rebuild; LOOK NOW is attention, "
        "not entry permission."
    )
    refined["location_semantics"] = "WATCH_RESET_OUTSIDE_FRESH_IGNITION_BAND"
    refined["fresh_ignition_location_max_pct"] = IGNITION_MAX_VWAP_DISTANCE_PCT
    refined["entry_authority_changed"] = False
    refined["anti_chase_authority_changed"] = False
    return refined


def _inherit(wrapper, wrapped) -> None:
    for name, value in getattr(wrapped, "__dict__", {}).items():
        if name.startswith("_gs") and not hasattr(wrapper, name):
            setattr(wrapper, name, value)


def install() -> None:
    """Refine only the already-cleaned extreme banner semantics."""
    from . import gs333_extreme_mover_operator_priority as extreme

    current = extreme.extreme_market_event
    if getattr(current, _OWNER, False):
        return

    @wraps(current)
    def extreme_market_event(record: dict) -> dict | None:
        return refine_extreme_event(current, record)

    _inherit(extreme_market_event, current)
    extreme_market_event._gs495_extreme_look_now_reset_language = True
    extreme_market_event._gs495_original = current
    setattr(extreme_market_event, _OWNER, True)
    extreme.extreme_market_event = extreme_market_event

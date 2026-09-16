"""GS474: keep LOOK NOW tied to a fresh bottom-up ignition transition.

Sep. 16 end-of-day validation showed one remaining operator-semantic leak after the
30s source was restored. A GS460 bottom-up compression can correctly earn LOOK NOW
when a new 30s/1m/3m/5m rung joins, but the presentation wrapper may continue to
render LOOK NOW after that fresh transition has aged out. That turns an urgent verb
into a persistent condition and can crowd the top of Walter's operator stack.

GS474 changes presentation only. It never blocks the initial GS460 LOOK NOW. It only
expires LOOK NOW when all of the following are true:
- the rendered LOOK NOW carries GS460 ST_FLIP_PRICE_COMPRESSION provenance; and
- GS460's own already-computed signal is no longer ``fresh_join``.

The record then returns to DEVELOPING with explicit language that the ignition is no
longer fresh and that Walter is waiting for a newly joined rung, reset/retest, or
other current evidence. Other LOOK NOW sources (fresh events, VWAP resets/retests,
JET FUEL, maturation, etc.) are untouched. No discovery, market-data request/value,
indicator formula, score, ranking, participation/structure decision, qualification,
readiness, alert authority, execution, session authority, or order behavior changes.
"""
from __future__ import annotations

from copy import deepcopy
from functools import wraps

_OWNER_ATTR = "_walter_gs474_fresh_look_now_expiry_owner"
_PROVENANCE = "ST_FLIP_PRICE_COMPRESSION"


def _compression_owned(state: dict) -> bool:
    provenance = list(state.get("attention_provenance") or [])
    return _PROVENANCE in provenance or bool(state.get("st_flip_compression"))


def fresh_look_now_state(original, record: dict) -> dict:
    """Expire only stale GS460 compression urgency; preserve every other state path."""
    from . import gs310_unified_opportunity_state as unified
    from . import gs460_st_flip_compression_ignition as gs460

    base = original(record)
    if str(base.get("state") or "") != unified.LOOK_NOW:
        return base
    if not _compression_owned(base):
        return base

    signal = gs460.st_flip_compression(record)
    if signal.get("fresh_join"):
        return base

    view = deepcopy(base)
    view["state"] = unified.DEVELOPING
    view["color"] = unified.STATE_COLORS[unified.DEVELOPING]
    view["st_flip_compression"] = signal
    view["reason"] = (
        "The bottom-up ST/VWAP ignition is no longer a fresh transition. The setup "
        "remains worth monitoring, but it has not earned a current LOOK NOW cue."
    )
    view["next_step"] = (
        "Keep it on watch for a newly joined timeframe rung, constructive reset/retest, "
        "or other fresh evidence before Walter elevates it again."
    )
    provenance = list(view.get("attention_provenance") or [])
    if "GS474_FRESH_LOOK_NOW_EXPIRY" not in provenance:
        provenance.append("GS474_FRESH_LOOK_NOW_EXPIRY")
    view["attention_provenance"] = provenance
    view["gs474_look_now_freshness"] = {
        "authority": "PRESENTATION_URGENCY_ONLY",
        "compression_active": bool(signal.get("active")),
        "fresh_join": bool(signal.get("fresh_join")),
        "entry_authority_changed": False,
        "alert_authority_changed": False,
    }
    return view


def _inherit(wrapper, wrapped) -> None:
    for name, value in getattr(wrapped, "__dict__", {}).items():
        if name.startswith("_gs") and not hasattr(wrapper, name):
            setattr(wrapper, name, value)


def install() -> None:
    """Install after GS468 as the final trader-facing LOOK NOW freshness boundary."""
    from . import gs310_unified_opportunity_state as unified
    from . import gs311_unified_voice as voice
    from . import gs314_state_consistency as consistency
    from . import gs363_operator_attention_hierarchy as hierarchy

    current = unified.opportunity_state
    if getattr(current, _OWNER_ATTR, False):
        calibrated = current
    else:
        @wraps(current)
        def calibrated(record: dict) -> dict:
            return fresh_look_now_state(current, record)

        _inherit(calibrated, current)
        calibrated._gs474_fresh_look_now_expiry = True
        calibrated._gs474_original = current
        setattr(calibrated, _OWNER_ATTR, True)
        unified.opportunity_state = calibrated

    voice.opportunity_state = calibrated
    consistency.opportunity_state = calibrated
    hierarchy.opportunity_state = calibrated

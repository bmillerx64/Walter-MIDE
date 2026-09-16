"""GS467: make LOOK NOW mean one consistent degree of operator urgency.

Live validation on 2026-09-16 exposed a semantic collision on FNGR. Walter displayed
LOOK NOW from GS393's permissive 1m ignition rule even though the newer bottom-up
30s -> 1m -> 3m model would classify the same shape as early-watch evidence unless
stronger structure joins.

GS467 is a final presentation adjudicator. It does not remove 1m reclaim/ST evidence;
it only prevents two legacy weak meanings from owning the yellow LOOK NOW state:

* generic current-attention alone;
* standalone GS393 1m VWAP reclaim / bullish 1m SuperTrend ignition.

A weak legacy LOOK NOW remains valid when current bottom-up evidence independently
supports urgency: either GS460 has active 30s->1m flip-price compression with flow,
or GS462 has JET FUEL (30s seed + supportive 1m + supportive 3m + flow). Existing
specific structural LOOK NOW reasons such as reset/retest, consolidation re-arm, and
fresh ST/VWAP maturation are left unchanged.

Demoted records remain visible as DEVELOPING / EARLY WATCH context. No discovery,
market-data request, indicator formula, threshold, qualification, readiness, alert
permission, execution rule, or order behavior changes.
"""
from __future__ import annotations

from copy import deepcopy
from functools import wraps

_LOOK_NOW_OWNER_ATTR = "_walter_gs467_look_now_semantics_owner"
_PROVENANCE = "GS467_LOOK_NOW_SEMANTICS"

_LEGACY_WEAK_PREFIXES = (
    "1m ignition:",
    "a current attention trigger says this symbol deserves a chart review",
    "current market-attention leader",
)


def legacy_weak_look_now(view: dict) -> bool:
    """Return True only for the two legacy LOOK NOW meanings GS467 is retiring."""
    reason = str(view.get("reason") or "").strip().lower()
    return any(reason.startswith(prefix) for prefix in _LEGACY_WEAK_PREFIXES)


def bottom_up_urgency(record: dict) -> dict:
    """Return current stronger evidence that may legitimately retain LOOK NOW."""
    from . import gs460_st_flip_compression_ignition as gs460
    from . import gs462_preflip_ignition_watch as gs462

    compression = gs460.st_flip_compression(record)
    preflip = gs462.preflip_ignition_watch(record)
    return {
        "compression": compression,
        "preflip": preflip,
        "strong": bool(compression.get("active") or preflip.get("jet_fuel")),
    }


def consolidated_look_now(original, record: dict) -> dict:
    """Demote only weak legacy LOOK NOW states that lack stronger current structure."""
    from . import gs310_unified_opportunity_state as unified

    base = original(record)
    if str(base.get("state") or "") != unified.LOOK_NOW:
        return base
    if not legacy_weak_look_now(base):
        return base

    urgency = bottom_up_urgency(record)
    if urgency.get("strong"):
        return base

    view = deepcopy(base)
    view["state"] = unified.DEVELOPING
    view["color"] = unified.STATE_COLORS[unified.DEVELOPING]

    provenance = list(view.get("attention_provenance") or [])
    if _PROVENANCE not in provenance:
        provenance.append(_PROVENANCE)
    view["attention_provenance"] = provenance

    preflip = urgency.get("preflip") or {}
    if preflip.get("active"):
        view["reason"] = (
            "EARLY WATCH: bottom-up 30s/1m attention is present, but the current "
            "structure has not yet earned LOOK NOW."
        )
    else:
        view["reason"] = (
            "Current 1m/attention evidence is worth monitoring, but it has not yet "
            "earned LOOK NOW."
        )
    view["next_step"] = (
        "Keep it visible and wait for stronger current structure: compressed 30s->1m "
        "ignition with flow, 3m JET FUEL, a constructive reset/retest, consolidation "
        "re-arm, or fresh ST/VWAP maturation."
    )
    view["look_now_semantics"] = {
        "legacy_reason_demoted": True,
        "bottom_up_compression": bool((urgency.get("compression") or {}).get("active")),
        "early_watch": bool(preflip.get("active")),
        "jet_fuel": bool(preflip.get("jet_fuel")),
        "authority": "PRESENTATION_ONLY",
    }
    return view


def _inherit(wrapper, wrapped) -> None:
    for name, value in getattr(wrapped, "__dict__", {}).items():
        if name.startswith("_gs") and not hasattr(wrapper, name):
            setattr(wrapper, name, value)


def install() -> None:
    """Install the final LOOK NOW semantic adjudicator across trader-facing bindings."""
    from . import gs310_unified_opportunity_state as unified
    from . import gs311_unified_voice as voice
    from . import gs314_state_consistency as consistency
    from . import gs363_operator_attention_hierarchy as hierarchy

    current = unified.opportunity_state
    if getattr(current, _LOOK_NOW_OWNER_ATTR, False):
        calibrated = current
    else:
        @wraps(current)
        def calibrated(record: dict) -> dict:
            return consolidated_look_now(current, record)

        _inherit(calibrated, current)
        calibrated._gs467_look_now_semantic_consolidation = True
        calibrated._gs467_original = current
        setattr(calibrated, _LOOK_NOW_OWNER_ATTR, True)
        unified.opportunity_state = calibrated

    voice.opportunity_state = calibrated
    consistency.opportunity_state = calibrated
    hierarchy.opportunity_state = calibrated

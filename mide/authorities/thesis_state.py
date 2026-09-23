"""Authoritative Walter Next Thesis / State boundary.

This module owns Walter's base trader-facing Opportunity State: the first place where
already-computed evidence becomes one coherent thesis. Historical GS modules may
still wrap the compatibility surface in gs310_unified_opportunity_state while they
are migrated one at a time, but the base meaning no longer lives in a numbered patch.

The public opportunity_state function intentionally resolves the current GS310
compatibility surface at call time. That preserves the complete validated late-runtime
wrapper chain during consolidation while base_opportunity_state remains the single
authoritative base interpretation.
"""

from __future__ import annotations

from copy import deepcopy
from functools import wraps
import math
import sys
from typing import Any


LOOK_NOW = "LOOK NOW"
DEVELOPING = "DEVELOPING"
WATCH_FOR_ENTRY = "WATCH FOR ENTRY"
CHASE_WAIT = "CHASE / WAIT"
HALTED = "HALTED"

STATE_COLORS = {
    LOOK_NOW: "#facc15",
    DEVELOPING: "#60a5fa",
    WATCH_FOR_ENTRY: "#4ade80",
    CHASE_WAIT: "#f59e0b",
    HALTED: "#f87171",
}


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


def _halted(record: dict) -> bool:
    if any(
        record.get(key) is True
        for key in ("halted", "is_halted", "suspended", "is_suspended")
    ):
        return True
    text = " ".join(
        str(record.get(key) or "")
        for key in ("halt_status", "trading_status", "market_status", "status_reason")
    ).lower()
    return "halt" in text or "suspend" in text


def _participation(record: dict) -> tuple[float | None, bool]:
    score = _number(record, "participation_surge_score", "participation_score")
    gate = record.get("participation_gate") or {}
    passed = gate.get("passed") is True or (score is not None and score >= 72.0)
    return score, passed


def _expansion(record: dict) -> tuple[float | None, bool]:
    score = _number(record, "expansion_quality", "expansion_score")
    passed = score is not None and score >= 58.0
    return score, passed


def _attention(record: dict) -> tuple[str, ...]:
    try:
        from mide.gs309_current_attention_mission import current_attention_provenance

        provenance = current_attention_provenance(record)
        if provenance:
            return provenance
    except Exception:
        pass
    evidence = []
    if str(record.get("headline") or "").strip():
        evidence.append("NEWS")
    if (_number(record, "volume_acceleration") or 0.0) > 1.0:
        evidence.append("VOLUME_ACCELERATION")
    return tuple(evidence)


def base_opportunity_state(record: dict) -> dict:
    """Return Walter's base current thesis from already-computed evidence."""
    relation = str(record.get("vwap_relation") or "").lower()
    distance = _number(record, "vwap_distance_pct")
    vwap_above = relation == "above"
    vwap_near = vwap_above and (distance is None or distance <= 2.0)
    trend = bool(record.get("supertrend_bullish") or record.get("supertrend_flip"))
    participation, participation_pass = _participation(record)
    expansion, expansion_pass = _expansion(record)
    acceleration = _number(record, "volume_acceleration") or 0.0
    attention = _attention(record)

    evidence = [
        {
            "label": "VWAP",
            "passed": vwap_near,
            "detail": "Above / within 2%"
            if vwap_near
            else ("Above but extended" if vwap_above else "Not above"),
        },
        {
            "label": "SuperTrend",
            "passed": trend,
            "detail": "Bullish" if trend else "Not confirmed",
        },
        {
            "label": "Participation",
            "passed": participation_pass,
            "detail": f"{participation:.0f}/100"
            if participation is not None
            else "Unavailable",
        },
        {
            "label": "Expansion",
            "passed": expansion_pass,
            "detail": f"{expansion:.0f}/100"
            if expansion is not None
            else "Unavailable",
        },
    ]

    if _halted(record):
        state = HALTED
        reason = "Trading is halted or suspended."
        next_step = (
            "Watch for resumption, then reassess fresh price, VWAP, trend, and volume."
        )
    elif not vwap_above:
        state = DEVELOPING
        if distance is not None and abs(distance) <= 2.0:
            reason = "Price is below VWAP; this is a reclaim watch, not an entry setup."
            next_step = (
                "Wait for price to reclaim and hold above VWAP before Walter elevates the setup."
            )
        else:
            reason = "Price is below VWAP; Walter will not elevate it for entry review."
            next_step = (
                "No entry review until price reclaims VWAP; then reassess trend, participation, and expansion."
            )
    elif distance is not None and distance > 2.0:
        state = CHASE_WAIT
        reason = f"Price is {distance:.1f}% above VWAP; the move is extended."
        next_step = (
            "Wait for a reset or constructive pullback toward VWAP before reconsidering."
        )
    elif vwap_near and trend and participation_pass and expansion_pass:
        state = WATCH_FOR_ENTRY
        reason = "VWAP, trend, participation, and expansion are aligned now."
        next_step = (
            "Review the chart for the actual entry; Walter is presenting, not authorizing, the trade."
        )
    elif vwap_above and trend and (
        participation_pass or expansion_pass or acceleration > 1.0
    ):
        state = DEVELOPING
        missing = [item["label"] for item in evidence if not item["passed"]]
        reason = (
            "Constructive price/trend structure is present, but the setup is still developing."
        )
        next_step = (
            "Need stronger " + " and ".join(missing[:2]).lower() + "."
            if missing
            else "Continue monitoring current evidence."
        )
    elif attention:
        state = LOOK_NOW
        reason = "A current attention trigger says this symbol deserves a chart review."
        next_step = (
            "Open the chart and confirm VWAP, SuperTrend, participation, and expansion."
        )
    else:
        state = DEVELOPING
        reason = (
            "Walter is still observing the symbol, but no immediate attention trigger is present."
        )
        next_step = "Keep it in the background until current evidence improves."

    return {
        "state": state,
        "color": STATE_COLORS[state],
        "reason": reason,
        "next_step": next_step,
        "attention_provenance": list(attention),
        "evidence": evidence,
    }


_LOOK_NOW_OWNER_ATTR = "_walter_gs467_look_now_semantics_owner"
_LOOK_NOW_PROVENANCE = "GS467_LOOK_NOW_SEMANTICS"


def legacy_1m_ignition_look_now(view: dict) -> bool:
    """Return True only for the legacy standalone 1m ignition reason."""
    reason = str(view.get("reason") or "").strip().lower()
    return reason.startswith("1m ignition:")


def bottom_up_urgency(record: dict) -> dict:
    """Return stronger current structure that may legitimately retain LOOK NOW."""
    from mide import gs460_st_flip_compression_ignition as gs460
    from mide import gs462_preflip_ignition_watch as gs462

    compression = gs460.st_flip_compression(record)
    preflip = gs462.preflip_ignition_watch(record)
    return {
        "compression": compression,
        "preflip": preflip,
        "strong": bool(compression.get("active") or preflip.get("jet_fuel")),
    }


def consolidated_look_now(original, record: dict) -> dict:
    """Demote only standalone 1m LOOK NOW when stronger structure is absent."""
    base = original(record)
    if str(base.get("state") or "") != LOOK_NOW:
        return base
    if not legacy_1m_ignition_look_now(base):
        return base

    urgency = bottom_up_urgency(record)
    if urgency.get("strong"):
        return base

    view = deepcopy(base)
    view["state"] = DEVELOPING
    view["color"] = STATE_COLORS[DEVELOPING]

    provenance = list(view.get("attention_provenance") or [])
    if _LOOK_NOW_PROVENANCE not in provenance:
        provenance.append(_LOOK_NOW_PROVENANCE)
    view["attention_provenance"] = provenance

    preflip = urgency.get("preflip") or {}
    if preflip.get("active"):
        view["reason"] = (
            "EARLY WATCH: bottom-up 30s/1m attention is present, but the current "
            "structure has not yet earned LOOK NOW."
        )
    else:
        view["reason"] = (
            "Current 1m VWAP/SuperTrend ignition is worth monitoring, but it has not "
            "yet earned LOOK NOW."
        )
    view["next_step"] = (
        "Keep it visible and wait for stronger current structure: compressed 30s->1m "
        "ignition with flow, 3m JET FUEL, a constructive reset/retest, consolidation "
        "re-arm, or fresh ST/VWAP maturation."
    )
    view["look_now_semantics"] = {
        "legacy_1m_ignition_demoted": True,
        "bottom_up_compression": bool((urgency.get("compression") or {}).get("active")),
        "early_watch": bool(preflip.get("active")),
        "jet_fuel": bool(preflip.get("jet_fuel")),
        "authority": "PRESENTATION_ONLY",
    }
    return view


def install_look_now_semantics() -> None:
    """Bind LOOK NOW adjudication at the historical GS467 compatibility position."""
    from mide import gs310_unified_opportunity_state as unified
    from mide import gs311_unified_voice as voice
    from mide import gs314_state_consistency as consistency
    from mide import gs363_operator_attention_hierarchy as hierarchy

    current = unified.opportunity_state
    if getattr(current, _LOOK_NOW_OWNER_ATTR, False):
        calibrated = current
    else:
        @wraps(current)
        def calibrated(record: dict) -> dict:
            return consolidated_look_now(current, record)

        _inherit_state_wrapper(calibrated, current)
        calibrated._gs467_look_now_semantic_consolidation = True
        calibrated._gs467_original = current
        setattr(calibrated, _LOOK_NOW_OWNER_ATTR, True)
        unified.opportunity_state = calibrated

    voice.opportunity_state = calibrated
    consistency.opportunity_state = calibrated
    hierarchy.opportunity_state = calibrated


_VWAP_TRUTH_OWNER_ATTR = "_walter_gs468_vwap_truth_veto_owner"
_VWAP_TRUTH_PROVENANCE = "GS468_NUMERIC_VWAP_VETO"


def _finite(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _vwap_pair(close: Any, vwap: Any, source: str) -> dict:
    close_n = _finite(close)
    vwap_n = _finite(vwap)
    available = close_n is not None and vwap_n not in (None, 0.0)
    if not available:
        return {
            "source": source,
            "available": False,
            "close": close_n,
            "vwap": vwap_n,
            "distance_pct": None,
            "above": None,
        }
    distance = (close_n - vwap_n) / vwap_n * 100.0
    return {
        "source": source,
        "available": True,
        "close": close_n,
        "vwap": vwap_n,
        "distance_pct": round(distance, 4),
        "above": bool(distance >= 0.0),
    }


def current_vwap_truth(record: dict) -> dict:
    """Return already-computed current numeric VWAP evidence without new data calls."""
    top = _vwap_pair(
        record.get("price"),
        record.get("vwap_value"),
        "snapshot_vs_primary_vwap",
    )

    one = dict((record.get("timeframes") or {}).get("1m") or {})
    one_close = one.get("current_close")
    one_vwap = one.get("current_vwap")
    if one_vwap is None:
        one_vwap = dict(one.get("st_vwap_line_cross") or {}).get("latest_vwap_value")
    one_pair = _vwap_pair(one_close, one_vwap, "1m_close_vs_primary_vwap")

    pairs = [item for item in (top, one_pair) if item.get("available")]
    below = [item for item in pairs if item.get("above") is False]
    above = [item for item in pairs if item.get("above") is True]
    return {
        "pairs": pairs,
        "numeric_below": bool(below),
        "numeric_above": bool(above),
        "below_sources": [item["source"] for item in below],
        "authority": "PRESENTATION_TRUTH_VETO_ONLY",
        "additional_market_data_requests": 0,
    }


def _numeric_below_record(record: dict, truth: dict) -> dict:
    """Return a detached state-input copy whose VWAP fields cannot contradict numbers."""
    view_record = deepcopy(record)
    pairs = list(truth.get("pairs") or [])
    below = [item for item in pairs if item.get("above") is False]
    if not below:
        return view_record

    chosen = next(
        (item for item in below if item.get("source") == "snapshot_vs_primary_vwap"),
        below[0],
    )
    view_record["vwap_relation"] = "below"
    distance = _finite(chosen.get("distance_pct"))
    if distance is not None:
        view_record["vwap_distance_pct"] = round(distance, 4)
    return view_record


def vwap_truth_state(original, record: dict) -> dict:
    """Apply the established numeric-below veto to a trader-facing thesis."""
    truth = current_vwap_truth(record)
    if not truth.get("numeric_below"):
        return original(record)

    state = original(_numeric_below_record(record, truth))
    view = deepcopy(state)

    if str(view.get("state") or "") in {LOOK_NOW, WATCH_FOR_ENTRY}:
        view["state"] = DEVELOPING
        view["color"] = STATE_COLORS[DEVELOPING]
        view["reason"] = (
            "Current numeric price/VWAP evidence is below VWAP; Walter will not elevate "
            "this setup until VWAP is reclaimed."
        )
        view["next_step"] = (
            "Keep it on background watch. Reassess only after current price and 1m "
            "structure reclaim VWAP."
        )

    provenance = list(view.get("attention_provenance") or [])
    if _VWAP_TRUTH_PROVENANCE not in provenance:
        provenance.append(_VWAP_TRUTH_PROVENANCE)
    view["attention_provenance"] = provenance
    view["vwap_truth_veto"] = truth
    return view


def _inherit_state_wrapper(wrapper, wrapped) -> None:
    for name, value in getattr(wrapped, "__dict__", {}).items():
        if name.startswith("_gs") and not hasattr(wrapper, name):
            setattr(wrapper, name, value)


def install_vwap_truth() -> None:
    """Bind numeric VWAP truth at the historical GS468 compatibility position."""
    from mide import gs310_unified_opportunity_state as unified
    from mide import gs311_unified_voice as voice
    from mide import gs314_state_consistency as consistency
    from mide import gs363_operator_attention_hierarchy as hierarchy

    current = unified.opportunity_state
    if getattr(current, _VWAP_TRUTH_OWNER_ATTR, False):
        calibrated = current
    else:
        @wraps(current)
        def calibrated(record: dict) -> dict:
            return vwap_truth_state(current, record)

        _inherit_state_wrapper(calibrated, current)
        calibrated._gs468_vwap_truth_veto = True
        calibrated._gs468_original = current
        setattr(calibrated, _VWAP_TRUTH_OWNER_ATTR, True)
        unified.opportunity_state = calibrated

    voice.opportunity_state = calibrated
    consistency.opportunity_state = calibrated
    hierarchy.opportunity_state = calibrated


def opportunity_state(record: dict) -> dict:
    """Return the fully calibrated current thesis through the compatibility surface.

    GS310 imports base_opportunity_state directly, so historical wrappers capture the
    base function rather than this resolver. Once those wrappers are installed, this
    resolver sees the current outer GS310 callable and delegates to it without
    recursion. When no wrapper is installed yet, it returns the authoritative base.
    """
    unified = sys.modules.get("mide.gs310_unified_opportunity_state")
    current = getattr(unified, "opportunity_state", None) if unified is not None else None
    if callable(current) and current is not base_opportunity_state:
        return current(record)
    return base_opportunity_state(record)


def __getattr__(name: str):
    """Resolve non-state collaborators lazily to avoid early package import cycles."""
    if name in {"behavioral_decision", "evaluate"}:
        from mide import decision_engine

        return getattr(decision_engine, name)
    if name in {
        "escalation_alert_phrase",
        "escalation_snapshot",
        "escalation_state_changes",
    }:
        from mide import escalation

        return getattr(escalation, name)
    if name == "mission_ranked_records":
        from mide.gs498_mission_ranking_direction import mission_ranked_records

        return mission_ranked_records
    if name == "walter_mission_control":
        from mide import ui

        return ui.walter_mission_control
    raise AttributeError(name)


__all__ = [
    "CHASE_WAIT",
    "DEVELOPING",
    "HALTED",
    "LOOK_NOW",
    "STATE_COLORS",
    "WATCH_FOR_ENTRY",
    "base_opportunity_state",
    "legacy_1m_ignition_look_now",
    "consolidated_look_now",
    "bottom_up_urgency",
    "current_vwap_truth",
    "behavioral_decision",
    "escalation_alert_phrase",
    "escalation_snapshot",
    "escalation_state_changes",
    "evaluate",
    "mission_ranked_records",
    "opportunity_state",
    "vwap_truth_state",
    "walter_mission_control",
]

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

import sys


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
    "behavioral_decision",
    "escalation_alert_phrase",
    "escalation_snapshot",
    "escalation_state_changes",
    "evaluate",
    "mission_ranked_records",
    "opportunity_state",
    "walter_mission_control",
]

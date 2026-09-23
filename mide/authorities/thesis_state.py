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


def state_with_ignition(original, record: dict) -> dict:
    """Interpret primary ignition evidence as trader-facing LOOK NOW meaning."""
    from mide.authorities import market_evidence

    base = original(record)
    evidence = market_evidence.ignition_evidence(record)
    if not evidence["recent"]:
        return base
    if base.get("state") in {
        WATCH_FOR_ENTRY,
        CHASE_WAIT,
        HALTED,
    }:
        return base

    view = deepcopy(base)
    view["state"] = LOOK_NOW
    view["color"] = STATE_COLORS[LOOK_NOW]
    trigger = evidence.get("trigger")
    if trigger == "VWAP_RECLAIM_WITH_BULLISH_1M_ST":
        view["reason"] = (
            "1m ignition: price freshly reclaimed/held VWAP while 1m SuperTrend is bullish."
        )
    else:
        view["reason"] = (
            "1m ignition: SuperTrend turned bullish while price is holding above VWAP."
        )
    view["next_step"] = (
        "Open the chart now. 3m confirmation may follow, but it is not required for "
        "chart review; do not chase if price extends beyond the VWAP guard."
    )
    provenance = list(view.get("attention_provenance") or [])
    if "FRESH_1M_IGNITION" not in provenance:
        provenance.append("FRESH_1M_IGNITION")
    view["attention_provenance"] = provenance
    return view


def install_ignition_state() -> None:
    """Bind GS393 ignition meaning at the historical state install position."""
    from mide import gs310_unified_opportunity_state as unified
    from mide import gs311_unified_voice as voice
    from mide import gs314_state_consistency as consistency
    from mide import gs363_operator_attention_hierarchy as hierarchy

    current = unified.opportunity_state
    if getattr(current, "_gs393_ignition_truth", False):
        calibrated = current
    else:
        original = current

        def calibrated(record: dict) -> dict:
            return state_with_ignition(original, record)

        _inherit_state_wrapper(calibrated, current)
        calibrated._gs393_ignition_truth = True
        calibrated._gs393_original = original
        unified.opportunity_state = calibrated

    voice.opportunity_state = calibrated
    consistency.opportunity_state = calibrated
    hierarchy.opportunity_state = calibrated


_LEADER_RESET_PROVENANCE = "PROVEN_LEADER_RESET_REIGNITION"
_LEADER_RESET_STATE_OWNER = "_walter_gs477_leader_reset_state_owner"


def leader_reset_opportunity_state(original, record: dict) -> dict:
    """Turn confirmed leader-reset evidence into state meaning without entry authority."""
    from mide.authorities import market_evidence

    base = original(record)
    evidence = record.get("leader_reset_reignition") or {}
    stage = str(evidence.get("stage") or "NONE")
    if stage == "NONE" or base.get("state") in {HALTED, WATCH_FOR_ENTRY}:
        return base

    view = deepcopy(base)
    provenance = list(view.get("attention_provenance") or [])
    if _LEADER_RESET_PROVENANCE not in provenance:
        provenance.append(_LEADER_RESET_PROVENANCE)
    view["attention_provenance"] = provenance
    view["leader_reset_reignition"] = evidence

    try:
        distance = float(evidence.get("current_vwap_distance_pct"))
    except (TypeError, ValueError):
        distance = None

    if stage == market_evidence.RESET_WATCH:
        prior = float(evidence.get("prior_max_vwap_distance_pct") or 0.0)
        current = abs(float(distance or 0.0))
        view["reason"] = (
            f"LEADER RESET WATCH: this mover was previously {prior:.1f}%+ above VWAP and "
            f"has reset to within {current:.1f}% of VWAP. 30s and 1m SuperTrend are bullish "
            "with participation/flow active."
        )
        view["next_step"] = (
            "Keep the chart open. Wait for primary VWAP reclaim; 3m SuperTrend confirmation "
            "adds ignition strength. This is attention only, not entry authority."
        )
        return view

    if (
        distance is None
        or distance < 0.0
        or distance > market_evidence.MAX_REIGNITION_VWAP_DISTANCE_PCT
    ):
        return view
    if base.get("state") == CHASE_WAIT:
        return view

    view["state"] = LOOK_NOW
    view["color"] = STATE_COLORS[LOOK_NOW]
    if stage == market_evidence.THREE_MINUTE_CONFIRMATION:
        view["reason"] = (
            "LEADER RE-IGNITION: primary VWAP is reclaimed after a constructive reset; "
            "30s, 1m and 3m SuperTrend are now bullish with participation/flow active."
        )
        view["next_step"] = (
            "Open the chart now. The 3m ignition rung has joined, but normal readiness, "
            "anti-chase and execution rules remain authoritative."
        )
    else:
        view["reason"] = (
            "LEADER RE-IGNITION: primary VWAP is reclaimed after a constructive reset; "
            "30s and 1m SuperTrend are bullish with participation/flow active. 3m is not "
            "yet confirmed by Walter's current evidence."
        )
        view["next_step"] = (
            "Open the chart now and watch the 3m SuperTrend rung. This is chart-review "
            "authority only; normal readiness, anti-chase and execution rules remain."
        )
    return view


def install_leader_reset_state() -> None:
    """Bind proven-leader reset meaning at the historical GS477 state position."""
    from mide import gs310_unified_opportunity_state as unified
    from mide import gs311_unified_voice as voice
    from mide import gs314_state_consistency as consistency
    from mide import gs363_operator_attention_hierarchy as hierarchy

    current = unified.opportunity_state
    if getattr(current, _LEADER_RESET_STATE_OWNER, False):
        calibrated = current
    else:
        @wraps(current)
        def calibrated(record: dict) -> dict:
            return leader_reset_opportunity_state(current, record)

        _inherit_state_wrapper(calibrated, current)
        calibrated._gs477_leader_reset_reignition = True
        calibrated._gs477_original = current
        setattr(calibrated, _LEADER_RESET_STATE_OWNER, True)
        unified.opportunity_state = calibrated

    voice.opportunity_state = calibrated
    consistency.opportunity_state = calibrated
    hierarchy.opportunity_state = calibrated


RETEST_DISCIPLINE_AUTHORITY = "PRESENTATION_DISCIPLINE_ONLY"
_RETEST_STATE_BIND_OWNER = "_walter_gs493_3m_st_retest_truth"
_RETEST_MEMORY_STATE_OWNER = "_walter_gs514_retest_event_memory_state"
_RETEST_DISCIPLINE_OWNER = "_walter_gs515_thesis_trigger_discipline"


def _fmt_retest_price(value) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "n/a"
    if abs(number) < 1:
        return f"{number:.4f}"
    if abs(number) < 10:
        return f"{number:.3f}"
    return f"{number:.2f}"


def _three_minute_guardrail_text(truth: dict) -> str:
    price = _fmt_retest_price(truth.get("price"))
    st_value = _fmt_retest_price(truth.get("three_minute_supertrend"))
    try:
        gap = float(truth.get("signed_gap_pct"))
    except (TypeError, ValueError):
        gap = None
    gap_text = "n/a" if gap is None else f"{abs(gap):.1f}%"
    near_limit = float(truth.get("near_st_line_limit_pct") or 2.0)

    if truth.get("state") == "ST_RETEST_CONFIRMED":
        return (
            f"NEAR 3M ST · PROXIMITY ONLY: price {price} is {gap_text} above the current "
            f"3m SuperTrend line {st_value}, inside Walter's existing "
            f"{near_limit:.0f}% near-ST band. Proximity alone does NOT prove a held retest."
        )
    if truth.get("state") == "3M_ST_LOST":
        relation = "below" if gap is not None and gap < 0 else "at"
        return (
            f"3M ST LOST / RECLAIM WATCH: price {price} is {gap_text} {relation} the "
            f"current 3m SuperTrend line {st_value}, or the 3m trend state is bearish. "
            "A prior retest thesis is no longer confirmed."
        )
    if truth.get("state") == "NOT_AT_3M_ST_YET":
        return (
            f"NOT AT 3M ST YET: price {price} remains {gap_text} above the current "
            f"3m SuperTrend line {st_value}. A VWAP touch does NOT count as a 3m "
            "SuperTrend retest."
        )
    return ""


def base_state_with_3m_st_truth(original, record: dict) -> dict:
    """Attach authoritative 3m-ST truth without changing the Opportunity State."""
    from mide.authorities import market_evidence

    base = original(record)
    truth = market_evidence.three_minute_st_retest_truth(record)
    if not truth.get("available"):
        return base

    view = deepcopy(base)
    view["three_minute_st_retest_truth"] = truth
    guardrail = _three_minute_guardrail_text(truth)
    if not guardrail:
        return view

    next_step = str(view.get("next_step") or "").strip()
    if guardrail not in next_step:
        view["next_step"] = f"{guardrail} {next_step}".strip()
    return view


# Public presentation seam. GS514 and GS515 compatibility installation may wrap this
# callable before GS493 binds it to the visible Opportunity State boundary.
state_with_3m_st_truth = base_state_with_3m_st_truth


def _supportive_timeframe(record: dict, label: str) -> bool:
    from mide.gs462_preflip_ignition_watch import _timeframe_detail

    detail = _timeframe_detail(record, label)
    return bool(
        detail.get("available")
        and detail.get("bullish")
        and detail.get("above_vwap")
    )


def discipline_sequence(record: dict, event: dict) -> dict:
    """Describe thesis-vs-trigger sequencing without creating entry authority."""
    relation = str(record.get("vwap_relation") or "").strip().lower()
    try:
        distance = float(record.get("vwap_distance_pct"))
    except (TypeError, ValueError):
        distance = None
    near_vwap = bool(relation == "above" and (distance is None or distance <= 2.0))
    thirty = _supportive_timeframe(record, "30s")
    one = _supportive_timeframe(record, "1m")
    repaired = bool(near_vwap and thirty and one)

    from mide.authorities import market_evidence

    return {
        "three_minute_retest_held": bool(event.get("active_memory")),
        "vwap_acceptance": near_vwap,
        "thirty_second_repaired": thirty,
        "one_minute_repaired": one,
        "lower_timeframe_repair_complete": repaired,
        "state": (
            "THESIS_HELD_TRIGGER_REPAIRED"
            if repaired
            else "THESIS_HELD_TRIGGER_INCOMPLETE"
        ),
        "authority": market_evidence.RETEST_MEMORY_AUTHORITY,
        "entry_authority_changed": False,
        "readiness_authority_changed": False,
    }


def retest_memory_state(state_helper, original, record: dict) -> dict:
    """Add remembered-retest sequencing to the established 3m truth guardrail."""
    from mide.authorities import market_evidence

    view = state_helper(original, record)
    truth = dict(view.get("three_minute_st_retest_truth") or {})
    if truth.get("state") != "PRIOR_ST_RETEST_HELD":
        return view

    event = dict(
        truth.get("prior_retest_event")
        or market_evidence.retest_event_from_record(record)
    )
    sequence = discipline_sequence(record, event)
    result = deepcopy(view)
    result["discipline_sequence"] = sequence

    try:
        age = float(event.get("age_seconds"))
    except (TypeError, ValueError):
        age = None
    age_text = f"{age / 60.0:.0f}m ago" if age is not None else "earlier"
    low_text = _fmt_retest_price(event.get("retest_low"))
    st_text = _fmt_retest_price(event.get("supertrend_at_retest"))
    near_limit = float(event.get("near_st_line_limit_pct") or 2.0)

    if sequence["lower_timeframe_repair_complete"]:
        guardrail = (
            f"PRIOR 3M ST RETEST HELD: low {low_text} tested the 3m SuperTrend "
            f"{st_text} {age_text} inside the existing {near_limit:.0f}% band. "
            "Lower-timeframe VWAP/30s/1m repair is now present; review the chart, "
            "but existing readiness and entry authority still control."
        )
    else:
        missing = []
        if not sequence["vwap_acceptance"]:
            missing.append("VWAP acceptance")
        if not sequence["thirty_second_repaired"]:
            missing.append("30s repair")
        if not sequence["one_minute_repaired"]:
            missing.append("1m repair")
        guardrail = (
            f"PRIOR 3M ST RETEST HELD: low {low_text} tested the 3m SuperTrend "
            f"{st_text} {age_text}. Thesis checkpoint confirmed; entry trigger is "
            "NOT earned yet. Still need " + ", ".join(missing) + "."
        )

    next_step = str(result.get("next_step") or "").strip()
    if "PRIOR 3M ST RETEST HELD:" not in next_step:
        result["next_step"] = f"{guardrail} {next_step}".strip()
    return result


def _sequence_line(sequence: dict) -> str:
    def mark(value: bool) -> str:
        return "✓" if value else "○"

    return (
        f"3m retest {mark(bool(sequence.get('three_minute_retest_held')))} · "
        f"VWAP {mark(bool(sequence.get('vwap_acceptance')))} · "
        f"30s {mark(bool(sequence.get('thirty_second_repaired')))} · "
        f"1m {mark(bool(sequence.get('one_minute_repaired')))}"
    )


def emphasize_discipline(view: dict) -> dict:
    """Make thesis-vs-trigger sequencing explicit without promoting state."""
    sequence = view.get("discipline_sequence") or {}
    if not isinstance(sequence, dict):
        return view

    state = str(sequence.get("state") or "")
    if state not in {
        "THESIS_HELD_TRIGGER_INCOMPLETE",
        "THESIS_HELD_TRIGGER_REPAIRED",
    }:
        return view

    result = deepcopy(view)
    existing_state = result.get("state")
    existing_color = result.get("color")
    evidence = list(result.get("evidence") or [])

    if state == "THESIS_HELD_TRIGGER_INCOMPLETE":
        result["discipline_label"] = "THESIS VALIDATED · TRIGGER NOT EARNED"
        result["discipline_ready"] = False
        existing_next = str(result.get("next_step") or "").strip()
        discipline_next = (
            "THESIS VALIDATED · TRIGGER NOT EARNED. "
            "The 3m retest held, but lower-timeframe repair is incomplete."
        )
        result["next_step"] = (
            f"{discipline_next} {existing_next}".strip()
            if discipline_next not in existing_next
            else existing_next
        )
        evidence.insert(
            0,
            {
                "label": "Entry sequence",
                "passed": False,
                "detail": _sequence_line(sequence),
            },
        )
    else:
        result["discipline_label"] = "THESIS VALIDATED · LOWER-TF REPAIR PRESENT"
        result["discipline_ready"] = True
        existing_next = str(result.get("next_step") or "").strip()
        discipline_next = (
            "THESIS VALIDATED · LOWER-TF REPAIR PRESENT. "
            "Review the chart, but Walter's existing full entry/readiness rules still control."
        )
        result["next_step"] = (
            f"{discipline_next} {existing_next}".strip()
            if discipline_next not in existing_next
            else existing_next
        )
        evidence.insert(
            0,
            {
                "label": "Entry sequence",
                "passed": True,
                "detail": _sequence_line(sequence),
            },
        )

    result["evidence"] = evidence
    result["discipline_authority"] = RETEST_DISCIPLINE_AUTHORITY
    result["state"] = existing_state
    if existing_color is not None:
        result["color"] = existing_color
    return result


def install_retest_memory_state() -> None:
    """Wrap the 3m truth presentation with held-retest memory before final binding."""
    global state_with_3m_st_truth
    current = state_with_3m_st_truth
    if getattr(current, _RETEST_MEMORY_STATE_OWNER, False):
        return

    @wraps(current)
    def bound_state(original, record: dict) -> dict:
        return retest_memory_state(current, original, record)

    setattr(bound_state, _RETEST_MEMORY_STATE_OWNER, True)
    bound_state._gs514_original = current
    state_with_3m_st_truth = bound_state


def install_retest_discipline() -> None:
    """Wrap remembered retest state with explicit thesis/trigger discipline."""
    global state_with_3m_st_truth
    current = state_with_3m_st_truth
    if getattr(current, _RETEST_DISCIPLINE_OWNER, False):
        return

    @wraps(current)
    def state_with_discipline(original, record: dict) -> dict:
        return emphasize_discipline(current(original, record))

    setattr(state_with_discipline, _RETEST_DISCIPLINE_OWNER, True)
    state_with_discipline._gs515_original = current
    state_with_3m_st_truth = state_with_discipline


def install_3m_st_retest_truth() -> None:
    """Bind the current retest presentation chain at the historical GS493 position."""
    from mide import gs310_unified_opportunity_state as unified
    from mide import gs311_unified_voice as voice
    from mide import gs314_state_consistency as consistency
    from mide import gs363_operator_attention_hierarchy as hierarchy

    current = unified.opportunity_state
    if getattr(current, _RETEST_STATE_BIND_OWNER, False):
        calibrated = current
    else:
        retest_view = state_with_3m_st_truth

        @wraps(current)
        def calibrated(record: dict) -> dict:
            return retest_view(current, record)

        _inherit_state_wrapper(calibrated, current)
        calibrated._gs493_3m_st_retest_truth = True
        calibrated._gs493_original = current
        setattr(calibrated, _RETEST_STATE_BIND_OWNER, True)
        unified.opportunity_state = calibrated

    voice.opportunity_state = calibrated
    consistency.opportunity_state = calibrated
    hierarchy.opportunity_state = calibrated


_FRESH_LOOK_NOW_OWNER_ATTR = "_walter_gs474_fresh_look_now_expiry_owner"
_COMPRESSION_PROVENANCE = "ST_FLIP_PRICE_COMPRESSION"


def _compression_owned(state: dict) -> bool:
    provenance = list(state.get("attention_provenance") or [])
    return _COMPRESSION_PROVENANCE in provenance or bool(state.get("st_flip_compression"))


def fresh_look_now_state(original, record: dict) -> dict:
    """Expire stale compression-owned LOOK NOW while preserving other urgency paths."""
    base = original(record)
    if str(base.get("state") or "") != LOOK_NOW:
        return base
    if not _compression_owned(base):
        return base

    from mide import gs460_st_flip_compression_ignition as gs460

    signal = gs460.st_flip_compression(record)
    if signal.get("fresh_join"):
        return base

    view = deepcopy(base)
    view["state"] = DEVELOPING
    view["color"] = STATE_COLORS[DEVELOPING]
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


def install_fresh_look_now_expiry() -> None:
    """Bind compression freshness at the historical GS474 position."""
    from mide import gs310_unified_opportunity_state as unified
    from mide import gs311_unified_voice as voice
    from mide import gs314_state_consistency as consistency
    from mide import gs363_operator_attention_hierarchy as hierarchy

    current = unified.opportunity_state
    if getattr(current, _FRESH_LOOK_NOW_OWNER_ATTR, False):
        calibrated = current
    else:
        @wraps(current)
        def calibrated(record: dict) -> dict:
            return fresh_look_now_state(current, record)

        _inherit_state_wrapper(calibrated, current)
        calibrated._gs474_fresh_look_now_expiry = True
        calibrated._gs474_original = current
        setattr(calibrated, _FRESH_LOOK_NOW_OWNER_ATTR, True)
        unified.opportunity_state = calibrated

    voice.opportunity_state = calibrated
    consistency.opportunity_state = calibrated
    hierarchy.opportunity_state = calibrated


FRESH_30S_ATTENTION_SECONDS = 5 * 60.0
_FRESH_ATTENTION_OWNER_ATTR = "_walter_gs525_fresh_attention_expiry_owner"
_FRESH_ATTENTION_PROVENANCE = "GS525_LATE_IGNITION_CONTEXT"


def thirty_second_flip_age(record: dict) -> float | None:
    """Return canonical 30s flip age from already-computed tripwire evidence."""
    age = _finite(record.get("supertrend_30s_last_flip_age_seconds"))
    if age is not None:
        return age
    tripwire = record.get("thirty_second_tripwire") or {}
    return _finite(tripwire.get("last_flip_age_seconds"))


def fresh_higher_maturation(record: dict) -> bool:
    """Reuse established fresh-rung truth; invent no new signal."""
    try:
        from mide import gs455_early_ignition_3m_confirmation as gs455

        signal = gs455.progression_signal(record)
        return bool(
            signal.get("active")
            and signal.get("new_rung") in {"1m", "3m", "5m", "10m", "15m"}
        )
    except Exception:
        return False


def stale_legacy_developing(record: dict, view: dict) -> bool:
    """Identify only the late standalone-ignition presentation case."""
    semantics = view.get("look_now_semantics") or {}
    if not semantics.get("legacy_1m_ignition_demoted"):
        return False
    if semantics.get("bottom_up_compression") or semantics.get("jet_fuel"):
        return False
    age = thirty_second_flip_age(record)
    if age is None or age <= FRESH_30S_ATTENTION_SECONDS:
        return False
    return not fresh_higher_maturation(record)


def tighten_late_attention_state(original, record: dict) -> dict:
    """Add truthful late-arrival context while preserving the canonical state."""
    view = original(record)
    if not stale_legacy_developing(record, view):
        return view

    age = thirty_second_flip_age(record)
    minutes = (age or 0.0) / 60.0
    updated = deepcopy(view)
    provenance = list(updated.get("attention_provenance") or [])
    if _FRESH_ATTENTION_PROVENANCE not in provenance:
        provenance.append(_FRESH_ATTENTION_PROVENANCE)
    updated["attention_provenance"] = provenance
    updated["reason"] = (
        f"LATE CONTINUATION WATCH: the earlier 30s ignition is {minutes:.1f} minutes "
        "old. Keep the runner visible, but do not treat this as fresh Developing urgency."
    )
    updated["next_step"] = (
        "Require a fresh 1m/3m maturation event, constructive reset/retest, VWAP reclaim, "
        "or renewed acceleration before elevating operator urgency again."
    )
    updated["freshness_semantics"] = {
        "late_legacy_ignition": True,
        "thirty_second_flip_age_seconds": age,
        "fresh_attention_limit_seconds": FRESH_30S_ATTENTION_SECONDS,
        "authority": "PRESENTATION_ONLY",
    }
    return updated


def install_fresh_attention_expiry() -> None:
    """Bind five-minute 30s attention freshness at the historical GS525 position."""
    from mide import gs310_unified_opportunity_state as unified
    from mide import gs311_unified_voice as voice
    from mide import gs314_state_consistency as consistency
    from mide import gs363_operator_attention_hierarchy as hierarchy
    from mide import gs462_preflip_ignition_watch as preflip

    preflip.RECENT_30S_FLIP_SECONDS = FRESH_30S_ATTENTION_SECONDS

    current = unified.opportunity_state
    if getattr(current, _FRESH_ATTENTION_OWNER_ATTR, False):
        calibrated = current
    else:
        @wraps(current)
        def calibrated(record: dict) -> dict:
            return tighten_late_attention_state(current, record)

        _inherit_state_wrapper(calibrated, current)
        calibrated._gs525_fresh_attention_expiry = True
        calibrated._gs525_original = current
        setattr(calibrated, _FRESH_ATTENTION_OWNER_ATTR, True)
        unified.opportunity_state = calibrated

    voice.opportunity_state = calibrated
    consistency.opportunity_state = calibrated
    hierarchy.opportunity_state = calibrated


MAX_DEVELOPING_3M_ST_GAP_PCT = 5.0
_STRETCH_OWNER_ATTR = "_walter_gs526_3m_stretch_semantics_owner"
_STRETCH_PROVENANCE = "GS526_3M_STRETCH_SEMANTICS"


def three_minute_st_retest_truth(record: dict) -> dict:
    """Read the existing GS493 3m-ST truth without creating a second definition."""
    from mide import gs493_3m_st_retest_truth as gs493

    return gs493.three_minute_st_retest_truth(record)


def materially_stretched_developing(record: dict, view: dict) -> tuple[bool, dict]:
    """Return whether an ordinary DEVELOPING card is already too far above 3m ST."""
    if str(view.get("state") or "") != DEVELOPING:
        return False, {}

    truth = three_minute_st_retest_truth(record)
    if truth.get("state") != "NOT_AT_3M_ST_YET":
        return False, truth
    if not truth.get("three_minute_bullish"):
        return False, truth

    try:
        gap = float(truth.get("signed_gap_pct"))
    except (TypeError, ValueError):
        return False, truth

    if gap <= MAX_DEVELOPING_3M_ST_GAP_PCT:
        return False, truth
    if fresh_higher_maturation(record):
        return False, truth
    return True, truth


def stretch_adjusted_state(original, record: dict) -> dict:
    """Convert only stale/extended DEVELOPING semantics to CHASE / WAIT."""
    view = original(record)
    stretched, truth = materially_stretched_developing(record, view)
    if not stretched:
        return view

    updated = deepcopy(view)
    updated["state"] = CHASE_WAIT
    updated["color"] = STATE_COLORS[CHASE_WAIT]

    gap = float(truth["signed_gap_pct"])
    price = truth.get("price")
    st_value = truth.get("three_minute_supertrend")
    updated["reason"] = (
        f"Price is still near VWAP, but it is already {gap:.1f}% above the bullish "
        "3m SuperTrend line. The move is no longer a fresh Developing setup."
    )
    updated["next_step"] = (
        "CHASE / WAIT. Keep the runner visible, but require a constructive reset, "
        "3m SuperTrend retest/reclaim, or a fresh higher-timeframe maturation event "
        "before elevating urgency again."
    )
    provenance = list(updated.get("attention_provenance") or [])
    if _STRETCH_PROVENANCE not in provenance:
        provenance.append(_STRETCH_PROVENANCE)
    updated["attention_provenance"] = provenance
    updated["three_minute_stretch_semantics"] = {
        "gap_pct": gap,
        "price": price,
        "three_minute_supertrend": st_value,
        "max_developing_gap_pct": MAX_DEVELOPING_3M_ST_GAP_PCT,
        "authority": "PRESENTATION_ONLY",
    }
    return updated


def install_3m_stretch_semantics() -> None:
    """Bind 3m-stretch anti-chase at the historical GS526 position."""
    from mide import gs310_unified_opportunity_state as unified
    from mide import gs311_unified_voice as voice
    from mide import gs314_state_consistency as consistency
    from mide import gs363_operator_attention_hierarchy as hierarchy

    current = unified.opportunity_state
    if getattr(current, _STRETCH_OWNER_ATTR, False):
        calibrated = current
    else:
        @wraps(current)
        def calibrated(record: dict) -> dict:
            return stretch_adjusted_state(current, record)

        _inherit_state_wrapper(calibrated, current)
        calibrated._gs526_3m_stretch_semantics = True
        calibrated._gs526_original = current
        setattr(calibrated, _STRETCH_OWNER_ATTR, True)
        unified.opportunity_state = calibrated

    voice.opportunity_state = calibrated
    consistency.opportunity_state = calibrated
    hierarchy.opportunity_state = calibrated


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
    "install_ignition_state",
    "state_with_ignition",
    "install_leader_reset_state",
    "leader_reset_opportunity_state",
    "install_3m_st_retest_truth",
    "install_retest_discipline",
    "install_retest_memory_state",
    "emphasize_discipline",
    "retest_memory_state",
    "discipline_sequence",
    "state_with_3m_st_truth",
    "base_state_with_3m_st_truth",
    "RETEST_DISCIPLINE_AUTHORITY",
    "stretch_adjusted_state",
    "materially_stretched_developing",
    "three_minute_st_retest_truth",
    "tighten_late_attention_state",
    "stale_legacy_developing",
    "fresh_higher_maturation",
    "thirty_second_flip_age",
    "fresh_look_now_state",
    "MAX_DEVELOPING_3M_ST_GAP_PCT",
    "FRESH_30S_ATTENTION_SECONDS",
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

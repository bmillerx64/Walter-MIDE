"""Authoritative Walter Next Presentation + Audio boundary.

Presentation consumes authoritative evidence/state and renders or announces it. Legacy
UI functions are resolved dynamically so importing this authority during startup can
never freeze an older wrapper implementation.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from copy import deepcopy
from functools import wraps
from typing import Any


def _ui_call(name: str, *args, **kwargs):
    from mide import ui
    return getattr(ui, name)(*args, **kwargs)


def actionable_candidate_records(*args, **kwargs):
    return _ui_call("actionable_candidate_records", *args, **kwargs)


def data_integrity_markup(*args, **kwargs):
    return _ui_call("data_integrity_markup", *args, **kwargs)


def decision_funnel_markup(*args, **kwargs):
    return _ui_call("decision_funnel_markup", *args, **kwargs)


def inject_css(*args, **kwargs):
    return _ui_call("inject_css", *args, **kwargs)


def market_session_quality_markup(*args, **kwargs):
    return _ui_call("market_session_quality_markup", *args, **kwargs)


def mission_control_header_markup(*args, **kwargs):
    return _ui_call("mission_control_header_markup", *args, **kwargs)


def opportunity_card(*args, **kwargs):
    return _ui_call("opportunity_card", *args, **kwargs)


def play_alert(*args, **kwargs):
    return _ui_call("play_alert", *args, **kwargs)


def radar_table(*args, **kwargs):
    return _ui_call("radar_table", *args, **kwargs)


def rejected_candidates_table(*args, **kwargs):
    return _ui_call("rejected_candidates_table", *args, **kwargs)


def rejection_diagnostics(*args, **kwargs):
    return _ui_call("rejection_diagnostics", *args, **kwargs)


def render_calibration_dashboard(*args, **kwargs):
    return _ui_call("render_calibration_dashboard", *args, **kwargs)


def render_early_setups(*args, **kwargs):
    return _ui_call("render_early_setups", *args, **kwargs)


def render_escalation_engine(*args, **kwargs):
    return _ui_call("render_escalation_engine", *args, **kwargs)


def render_live_opportunity_feed(*args, **kwargs):
    return _ui_call("render_live_opportunity_feed", *args, **kwargs)


def render_walter_mission_control(*args, **kwargs):
    return _ui_call("render_walter_mission_control", *args, **kwargs)


def scanner_v2_dashboard_counts(*args, **kwargs):
    return _ui_call("scanner_v2_dashboard_counts", *args, **kwargs)


def scanner_v2_display_sections(*args, **kwargs):
    return _ui_call("scanner_v2_display_sections", *args, **kwargs)


def render_sidebar_audio_health(*args, **kwargs):
    from mide.gs516_visible_alert_audio_health import render_sidebar_audio_health as current
    return current(*args, **kwargs)


def render_live_evidence_diagnostics(*args, **kwargs):
    from mide.live_evidence_observation import render_live_evidence_diagnostics as current
    return current(*args, **kwargs)


# ---------------------------------------------------------------------------
# Authoritative operator ordering
# ---------------------------------------------------------------------------
#
# Historically the final card order accumulated as nested GS463 -> GS465 ->
# GS497 -> GS517 -> GS539 wrappers. Walter Next keeps the same staged semantics
# but owns them in one Presentation + Audio wrapper. Each historical installer
# activates its stage at the same point in startup; no additional wrapper is added.

_OPERATOR_ORDER_OWNER = "_walter_next_authoritative_operator_order_owner"

STATE_FIRST_WATCH_FOR_ENTRY_BAND = 60
STATE_FIRST_LOOK_NOW_BAND = 50
STATE_FIRST_JET_FUEL_BAND = 47
STATE_FIRST_EARLY_WATCH_BAND = 46
STATE_FIRST_FRESH_MATURATION_BAND = 45
STATE_FIRST_TRAJECTORY_BAND = 44
STATE_FIRST_RECENT_CONFIRMATION_BAND = 43
STATE_FIRST_DEVELOPING_BAND = 30
STATE_FIRST_CHASE_WAIT_BAND = 20
STATE_FIRST_OTHER_BAND = 10

CONTIGUOUS_WATCH_FOR_ENTRY_BAND = 60
CONTIGUOUS_LOOK_NOW_BAND = 50
CONTIGUOUS_DEVELOPING_BAND = 40
CONTIGUOUS_CHASE_WAIT_BAND = 30
CONTIGUOUS_HALTED_BAND = 20
CONTIGUOUS_OTHER_BAND = 10

_OPERATOR_ORDER_STAGE_SEQUENCE = (
    "state_first",
    "state_contiguous",
    "rank_aware",
    "fresh_event",
    "pe_strength",
)

_OPERATOR_ORDER_STAGE_METADATA = {
    "state_first": (
        "_gs463_state_first_operator_order",
        "_gs463_original",
    ),
    "state_contiguous": (
        "_gs465_presentation_priority_cleanup",
        "_gs465_original",
    ),
    "rank_aware": (
        "_gs497_rank_aware_attention_order",
        "_gs497_original",
    ),
    "fresh_event": (
        "_gs517_fresh_event_priority",
        "_gs517_original",
    ),
    "pe_strength": (
        "_gs539_pe_strength_order",
        "_gs539_original",
    ),
}


def effective_operator_attention_band(record: dict) -> int:
    """Return the historical GS463 state/attention presentation band."""
    from mide import gs310_unified_opportunity_state as unified
    from mide import gs457_maturation_leader_priority as gs457
    from mide import gs459_price_trajectory_attention as gs459
    from mide import gs462_preflip_ignition_watch as gs462

    state = str(unified.opportunity_state(record).get("state") or "")
    if state == unified.WATCH_FOR_ENTRY:
        return STATE_FIRST_WATCH_FOR_ENTRY_BAND
    if state == unified.LOOK_NOW:
        return STATE_FIRST_LOOK_NOW_BAND

    preflip = gs462.preflip_ignition_watch(record)
    if preflip.get("active"):
        return (
            STATE_FIRST_JET_FUEL_BAND
            if preflip.get("jet_fuel")
            else STATE_FIRST_EARLY_WATCH_BAND
        )

    maturation = gs457.maturation_attention(record)
    if maturation.get("fresh_maturation"):
        return STATE_FIRST_FRESH_MATURATION_BAND

    if gs459.trajectory_attention(record).get("active"):
        return STATE_FIRST_TRAJECTORY_BAND

    if maturation.get("sustained_confirmation"):
        return STATE_FIRST_RECENT_CONFIRMATION_BAND

    if state == unified.DEVELOPING:
        return STATE_FIRST_DEVELOPING_BAND
    if state == unified.CHASE_WAIT:
        return STATE_FIRST_CHASE_WAIT_BAND
    return STATE_FIRST_OTHER_BAND


def _state_first_stage(rows: list[dict]) -> list[dict]:
    output = list(rows)
    output.sort(key=effective_operator_attention_band, reverse=True)
    return output


def ordered_state_first_records(
    records: list[dict],
    baseline_order=None,
) -> list[dict]:
    rows = list(baseline_order(records) if baseline_order is not None else (records or []))
    return _state_first_stage(rows)


def strict_state_band(record: dict) -> int:
    """Return the historical GS465 non-negotiable visible state band."""
    from mide import gs310_unified_opportunity_state as unified

    state = str(unified.opportunity_state(record).get("state") or "")
    if state == unified.WATCH_FOR_ENTRY:
        return CONTIGUOUS_WATCH_FOR_ENTRY_BAND
    if state == unified.LOOK_NOW:
        return CONTIGUOUS_LOOK_NOW_BAND
    if state == unified.DEVELOPING:
        return CONTIGUOUS_DEVELOPING_BAND
    if state == unified.CHASE_WAIT:
        return CONTIGUOUS_CHASE_WAIT_BAND
    if state == unified.HALTED:
        return CONTIGUOUS_HALTED_BAND
    return CONTIGUOUS_OTHER_BAND


def attention_tiebreak(record: dict) -> tuple[int, float, float]:
    """Rank attention evidence only inside an already-equal Opportunity State."""
    from mide import gs457_maturation_leader_priority as gs457
    from mide import gs459_price_trajectory_attention as gs459
    from mide import gs462_preflip_ignition_watch as gs462

    preflip = gs462.preflip_ignition_watch(record)
    if preflip.get("active"):
        one_gap = (preflip.get("one_minute") or {}).get("st_gap_pct")
        three_gap = (preflip.get("three_minute") or {}).get("st_gap_pct")
        try:
            one_gap = float(one_gap)
        except (TypeError, ValueError):
            one_gap = 999.0
        try:
            three_gap = float(three_gap)
        except (TypeError, ValueError):
            three_gap = 999.0
        return (60 if preflip.get("jet_fuel") else 55, -one_gap, -three_gap)

    maturation = gs457.maturation_attention(record)
    if maturation.get("fresh_maturation"):
        return (50, 0.0, 0.0)
    if gs459.trajectory_attention(record).get("active"):
        return (45, 0.0, 0.0)
    if maturation.get("sustained_confirmation"):
        return (40, 0.0, 0.0)
    return (0, 0.0, 0.0)


def _state_contiguous_stage(rows: list[dict]) -> list[dict]:
    output = list(rows)
    output.sort(key=attention_tiebreak, reverse=True)
    output.sort(key=strict_state_band, reverse=True)
    return output


def ordered_state_contiguous_records(
    records: list[dict],
    baseline_order=None,
) -> list[dict]:
    rows = list(baseline_order(records) if baseline_order is not None else (records or []))
    return _state_contiguous_stage(rows)


def current_mission_rank(record: dict) -> int | None:
    """Return a current positive Mission Ranking, rejecting stale terminal residue."""
    value = record.get("mission_rank")
    try:
        rank = int(float(value))
    except (TypeError, ValueError):
        return None
    if rank <= 0:
        return None

    terminal_stage = str(record.get("terminal_stage") or "").strip()
    terminal_outcome = str(record.get("terminal_outcome") or "").strip().lower()
    if terminal_stage and terminal_stage != "Mission Ranking and Publication":
        return None
    if terminal_outcome and "ranked" not in terminal_outcome:
        return None
    return rank


def _rank_aware_stage(rows: list[dict]) -> list[dict]:
    from mide import gs310_unified_opportunity_state as unified

    ready: list[dict] = []
    ranked: list[dict] = []
    unranked: list[dict] = []
    halted: list[dict] = []

    for record in rows:
        try:
            state = str(unified.opportunity_state(record).get("state") or "")
        except Exception:
            state = ""
        if state == unified.WATCH_FOR_ENTRY:
            ready.append(record)
        elif state == unified.HALTED:
            halted.append(record)
        elif current_mission_rank(record) is not None:
            ranked.append(record)
        else:
            unranked.append(record)

    ranked.sort(key=lambda record: current_mission_rank(record) or 10**9)
    return ready + ranked + unranked + halted


def ordered_rank_aware_records(
    records: Iterable[dict],
    *,
    baseline_order: Callable[[list[dict]], list[dict]] | None = None,
) -> list[dict]:
    source = list(records or [])
    rows = list(baseline_order(source) if baseline_order is not None else source)
    return _rank_aware_stage(rows)


def fresh_maturation_event(record: dict) -> bool:
    """Return current GS455 maturation-event truth without inventing thresholds."""
    from mide import gs310_unified_opportunity_state as unified
    from mide import gs455_early_ignition_3m_confirmation as gs455

    try:
        state = str(unified.opportunity_state(record).get("state") or "")
    except Exception:
        state = ""
    if state in {unified.WATCH_FOR_ENTRY, unified.HALTED}:
        return False
    try:
        return bool(gs455.progression_signal(record).get("active"))
    except Exception:
        return False


def _fresh_event_stage(rows: list[dict]) -> list[dict]:
    from mide import gs310_unified_opportunity_state as unified

    def attention_band(record: dict) -> int:
        try:
            state = str(unified.opportunity_state(record).get("state") or "")
        except Exception:
            state = ""
        if state == unified.WATCH_FOR_ENTRY:
            return 3
        if state == unified.HALTED:
            return 0
        if fresh_maturation_event(record):
            return 2
        return 1

    output = list(rows)
    output.sort(key=attention_band, reverse=True)
    return output


def ordered_fresh_event_records(
    records: Iterable[dict],
    *,
    baseline_order: Callable[[list[dict]], list[dict]] | None = None,
) -> list[dict]:
    source = list(records or [])
    rows = list(baseline_order(source) if baseline_order is not None else source)
    return _fresh_event_stage(rows)


def _pe_number(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def participation_value(record: dict) -> float | None:
    for key in ("participation_surge_score", "participation_score"):
        value = _pe_number(record.get(key))
        if value is not None:
            return value
    return None


def expansion_value(record: dict) -> float | None:
    for key in ("expansion_quality", "expansion_score"):
        value = _pe_number(record.get(key))
        if value is not None:
            return value
    return None


def pe_strength_score(record: dict) -> float | None:
    participation = participation_value(record)
    expansion = expansion_value(record)
    if participation is None or expansion is None:
        return None
    return (participation + expansion) / 2.0


def _pe_halted(record: dict) -> bool:
    if any(
        record.get(key) is True
        for key in ("halted", "is_halted", "suspended", "is_suspended")
    ):
        return True
    text = " ".join(
        str(record.get(key) or "")
        for key in ("halt_status", "trading_status", "market_status", "status_reason")
    ).casefold()
    return "halt" in text or "suspend" in text


def _pe_strength_stage(rows: list[dict]) -> list[dict]:
    output = list(rows)
    output.sort(
        key=lambda record: (
            pe_strength_score(record)
            if pe_strength_score(record) is not None
            else float("-inf")
        ),
        reverse=True,
    )
    output.sort(
        key=lambda record: bool(record.get("qualified_for_entry") is True),
        reverse=True,
    )
    output.sort(key=_pe_halted)
    return output


def ordered_pe_strength_records(
    records: Iterable[dict],
    *,
    baseline_order: Callable[[list[dict]], list[dict]] | None = None,
) -> list[dict]:
    source = list(records or [])
    rows = list(baseline_order(source) if baseline_order is not None else source)
    return _pe_strength_stage(rows)


def _apply_operator_order_stages(
    rows: list[dict],
    active_stages: set[str],
) -> list[dict]:
    output = list(rows)
    for stage in _OPERATOR_ORDER_STAGE_SEQUENCE:
        if stage not in active_stages:
            continue
        if stage == "state_first":
            output = _state_first_stage(output)
        elif stage == "state_contiguous":
            output = _state_contiguous_stage(output)
        elif stage == "rank_aware":
            output = _rank_aware_stage(output)
        elif stage == "fresh_event":
            output = _fresh_event_stage(output)
        elif stage == "pe_strength":
            output = _pe_strength_stage(output)
    return output


def activate_operator_order_stage(stage: str) -> None:
    """Activate one historical ordering stage inside one authoritative wrapper."""
    if stage not in _OPERATOR_ORDER_STAGE_SEQUENCE:
        raise ValueError(f"unknown operator-order stage: {stage}")

    from mide import gs369_escalation_priority_order as gs369

    current = gs369.ordered_escalation_records
    if getattr(current, _OPERATOR_ORDER_OWNER, False):
        wrapper = current
    else:
        baseline = current

        def ordered_escalation_records(records: list[dict]) -> list[dict]:
            rows = list(baseline(records))
            active = set(
                getattr(
                    ordered_escalation_records,
                    "_walter_next_operator_order_stages",
                    set(),
                )
            )
            return _apply_operator_order_stages(rows, active)

        _inherit_audio_wrapper(ordered_escalation_records, baseline)
        setattr(ordered_escalation_records, _OPERATOR_ORDER_OWNER, True)
        ordered_escalation_records._walter_next_operator_order_stages = set()
        ordered_escalation_records._walter_next_operator_order_baseline = baseline
        gs369.ordered_escalation_records = ordered_escalation_records
        wrapper = ordered_escalation_records

    active = set(getattr(wrapper, "_walter_next_operator_order_stages", set()))
    active.add(stage)
    wrapper._walter_next_operator_order_stages = active

    marker, original_attr = _OPERATOR_ORDER_STAGE_METADATA[stage]
    setattr(wrapper, marker, True)
    if not hasattr(wrapper, original_attr):
        setattr(
            wrapper,
            original_attr,
            getattr(wrapper, "_walter_next_operator_order_baseline", None),
        )


_PE_STRENGTH_STATE_OWNER = "_walter_gs539_pe_strength_state_owner"


def state_with_pe_strength(original, record: dict) -> dict:
    """Explain visible P/E Strength without changing Opportunity State/color."""
    view = original(record)
    score = pe_strength_score(record)
    if score is None:
        return view
    result = deepcopy(view)
    result["pe_strength_score"] = round(score, 1)
    reason = str(result.get("reason") or "").strip()
    prefix = f"P/E Strength {score:.0f}/100"
    if not reason.startswith("P/E Strength "):
        result["reason"] = f"{prefix} · {reason}".strip(" ·")
    return result


def install_pe_strength_state() -> None:
    """Bind the historical GS539 explanatory state wrapper."""
    from mide import gs310_unified_opportunity_state as unified
    from mide import gs311_unified_voice as voice
    from mide import gs314_state_consistency as consistency
    from mide import gs363_operator_attention_hierarchy as hierarchy

    current_state = unified.opportunity_state
    if getattr(current_state, _PE_STRENGTH_STATE_OWNER, False):
        calibrated = current_state
    else:
        @wraps(current_state)
        def calibrated(record: dict) -> dict:
            return state_with_pe_strength(current_state, record)

        _inherit_audio_wrapper(calibrated, current_state)
        calibrated._gs539_pe_strength_order = True
        calibrated._gs539_original = current_state
        setattr(calibrated, _PE_STRENGTH_STATE_OWNER, True)
        unified.opportunity_state = calibrated

    voice.opportunity_state = calibrated
    consistency.opportunity_state = calibrated
    hierarchy.opportunity_state = calibrated


def install_pe_strength_order() -> None:
    install_pe_strength_state()
    activate_operator_order_stage("pe_strength")


FRESH_3M_SECONDS = 180.0
_MATURATION_AUDIO_OWNER = "_walter_gs492_maturation_transition_audio"
_AUDIO_GATE_BRIDGE_OWNER = "_walter_gs512_audio_architecture_gate_bridge"

_AUDIO_STAGE_BY_GATE = {
    "participation_gate": "Participation Assessment",
    "structure_gate": "Expansion Assessment",
}


def _audio_number(value: Any) -> float | None:
    try:
        return float(value) if value is not None and value != "" else None
    except (TypeError, ValueError):
        return None


def _audio_decision(record: dict) -> dict:
    value = record.get("decision_time_evidence") or {}
    return value if isinstance(value, dict) else {}


def _audio_field(record: dict, key: str, default=None):
    if key in record and record.get(key) is not None:
        return record.get(key)
    return _audio_decision(record).get(key, default)


def _audio_normalized(value: Any) -> str:
    return " ".join(str(value or "").strip().upper().split())


def _maturation_attention_label(record: dict) -> bool:
    return bool(
        _audio_normalized(_audio_field(record, "status")) == "WATCH NOW"
        or _audio_normalized(_audio_field(record, "candidate_status")) == "ENTRY READY"
    )


def _previous_maturation_attention(record: dict) -> bool:
    previous = record.get("opportunity_pulse_previous") or {}
    return (
        isinstance(previous, dict)
        and bool(previous)
        and _maturation_attention_label(previous)
    )


def _legacy_audio_gate_passed(record: dict, name: str) -> bool:
    value = record.get(name)
    if not isinstance(value, dict):
        value = _audio_decision(record).get(name) or {}
    return isinstance(value, dict) and value.get("passed") is True


# Deliberately starts with the historical GS492 rule. GS512's compatibility install
# rebinds this at its original position after the maturation-audio layer exists.
_maturation_gate_passed = _legacy_audio_gate_passed


def authoritative_gate_passed(record: dict, name: str) -> bool:
    """Resolve audio gate truth from explicit dictionaries, then Architecture-v1 audit."""
    direct = record.get(name)
    if isinstance(direct, dict) and "passed" in direct:
        return direct.get("passed") is True

    evidence = record.get("decision_time_evidence") or {}
    if isinstance(evidence, dict):
        nested = evidence.get(name)
        if isinstance(nested, dict) and "passed" in nested:
            return nested.get("passed") is True

    stage = _AUDIO_STAGE_BY_GATE.get(str(name))
    if not stage:
        return False

    from mide.gs303_flight_recorder_authoritative_funnel import _gate_from_audit, _stage_audit

    compatibility = _gate_from_audit(_stage_audit(record, stage))
    return compatibility.get("passed") is True


def _maturation_timeframes(record: dict) -> dict:
    value = record.get("timeframes")
    if not isinstance(value, dict):
        value = _audio_decision(record).get("timeframes") or {}
    return value if isinstance(value, dict) else {}


def _maturation_tf(record: dict, label: str) -> dict:
    detail = _maturation_timeframes(record).get(label) or {}
    if not isinstance(detail, dict):
        return {}
    bullish = bool(
        detail.get("current_supertrend_bullish")
        if "current_supertrend_bullish" in detail
        else detail.get("supertrend_bullish", detail.get("supertrend"))
    )
    above = bool(
        detail.get("current_above_vwap")
        if "current_above_vwap" in detail
        else detail.get("above_vwap")
    )
    return {
        "raw": detail,
        "supportive": bool(
            detail.get("data_available") is not False and bullish and above
        ),
        "bullish": bullish,
        "above_vwap": above,
    }


def _maturation_cross_new(detail: dict) -> bool:
    raw = detail.get("raw") or {}
    cross = raw.get("st_vwap_line_cross") or {}
    return isinstance(cross, dict) and cross.get("new") is True


def _three_minute_maturation_fresh(detail: dict) -> bool:
    raw = detail.get("raw") or {}
    age = _audio_number(raw.get("bullish_flip_age_seconds"))
    return bool(age is not None and 0.0 <= age <= FRESH_3M_SECONDS)


def maturation_transition(record: dict) -> dict:
    """Return presentation-only runner maturation truth from current evidence."""
    thirty = _maturation_tf(record, "30s")
    one = _maturation_tf(record, "1m")
    three = _maturation_tf(record, "3m")
    gates = bool(
        _maturation_gate_passed(record, "participation_gate")
        and _maturation_gate_passed(record, "structure_gate")
    )
    two_rung = bool(thirty.get("supportive") and one.get("supportive"))
    three_rung = bool(two_rung and three.get("supportive"))
    structure_fresh = bool(
        _three_minute_maturation_fresh(three)
        or _maturation_cross_new(thirty)
        or _maturation_cross_new(one)
    )

    stage = "NONE"
    if gates and three_rung and structure_fresh:
        stage = "RUNNER_DETECTED"
    elif (
        gates
        and two_rung
        and _maturation_attention_label(record)
        and not _previous_maturation_attention(record)
    ):
        stage = "RUNNER_BUILDING"

    return {
        "active": stage != "NONE",
        "stage": stage,
        "symbol": str(
            record.get("symbol") or _audio_decision(record).get("symbol") or ""
        ).strip().upper(),
        "gates_passed": gates,
        "thirty_second_supportive": bool(thirty.get("supportive")),
        "one_minute_supportive": bool(one.get("supportive")),
        "three_minute_supportive": bool(three.get("supportive")),
        "structure_fresh": structure_fresh,
        "vwap_distance_pct": _audio_number(_audio_field(record, "vwap_distance_pct")),
        "qualified_for_entry": bool(_audio_field(record, "qualified_for_entry") is True),
        "qualified_for_alert": bool(_audio_field(record, "qualified_for_alert") is True),
        "authority": "OPERATOR_ATTENTION_AUDIO_ONLY",
        "entry_authority_changed": False,
        "alert_authority_changed": False,
    }


def maturation_audio_phrase(records: list[dict]) -> str:
    """Speak one fresh runner-maturation event without granting entry authority."""
    for record in records or []:
        event = maturation_transition(record)
        if not event.get("active") or not event.get("symbol"):
            continue
        symbol = event["symbol"]
        if event["stage"] == "RUNNER_DETECTED":
            phrase = (
                f"{symbol}. RUNNER DETECTED. LOOK NOW. "
                "30 second, 1 minute, and 3 minute structure are aligned above VWAP."
            )
        else:
            phrase = (
                f"{symbol}. RUNNER BUILDING. LOOK NOW. "
                "30 second and 1 minute structure are aligned; 3 minute confirmation is pending."
            )
        distance = event.get("vwap_distance_pct")
        if distance is not None and distance > 5.0:
            phrase += (
                f" Extended {distance:.1f} percent above VWAP. "
                "Do not chase; watch for a reset."
            )
        else:
            phrase += " Attention only; normal entry rules still apply."
        return phrase
    return ""


def install_maturation_transition_audio() -> None:
    """Bind maturation-event audio at the historical GS492 position."""
    from mide import escalation
    from mide.gs365_chime_semantic_classifier import semantic_chime_count

    current = escalation.escalation_alert_phrase
    if getattr(current, _MATURATION_AUDIO_OWNER, False):
        return

    @wraps(current)
    def alert_phrase(records: list[dict]) -> str:
        rows = list(records or [])
        established = current(rows)
        if established and semantic_chime_count(established) >= 3:
            return established
        maturation = maturation_audio_phrase(rows)
        return maturation or established

    _inherit_audio_wrapper(alert_phrase, current)
    alert_phrase._gs492_maturation_transition_audio = True
    alert_phrase._gs492_original = current
    setattr(alert_phrase, _MATURATION_AUDIO_OWNER, True)
    escalation.escalation_alert_phrase = alert_phrase


def install_audio_architecture_gate_bridge() -> None:
    """Activate Architecture-v1 gate fallback at the historical GS512 position."""
    global _maturation_gate_passed

    from mide import gs473_operator_attention_audio as gs473

    _maturation_gate_passed = authoritative_gate_passed
    gs473._gate_passed = authoritative_gate_passed


_LEADER_RESET_AUDIO_OWNER = "_walter_gs477_leader_reset_audio_owner"


def augment_leader_reset_records(records: list[dict], visible: list[dict]) -> list[dict]:
    """Keep an active reset/re-ignition visible as awareness only when needed."""
    from mide.gs375_operator_awareness import awareness_record

    output = list(visible or [])
    present = {
        str(record.get("symbol") or "").strip().upper()
        for record in output
        if str(record.get("symbol") or "").strip()
    }
    for record in records or []:
        evidence = record.get("leader_reset_reignition") or {}
        symbol = str(record.get("symbol") or "").strip().upper()
        if not symbol or symbol in present or not evidence.get("active"):
            continue
        output.append(awareness_record(record))
        present.add(symbol)
    return output


def enrich_visible_records(records: list[dict], actionable_function) -> list[dict]:
    """Enrich a detached render snapshot without replacing the public UI callable."""
    from mide.authorities import market_evidence

    enriched = market_evidence.apply_leader_reset_marks(records)
    visible = list(actionable_function(enriched) or [])
    return augment_leader_reset_records(enriched, visible)


def leader_reset_audio_phrase(records: list[dict]) -> str:
    """Speak one fresh reset transition without implying a trade instruction."""
    from mide.authorities import market_evidence

    for record in records or []:
        evidence = record.get("leader_reset_reignition") or {}
        if not evidence.get("stage_fresh"):
            continue
        symbol = str(record.get("symbol") or "").strip().upper()
        if not symbol:
            continue
        stage = evidence.get("stage")
        if stage == market_evidence.RESET_WATCH:
            distance = abs(float(evidence.get("current_vwap_distance_pct") or 0.0))
            return (
                f"{symbol}. RESET WATCH. Proven leader is back within {distance:.1f} percent "
                "of VWAP with 30 second and 1 minute SuperTrend bullish. Watch the reclaim. "
                "Attention only."
            )
        if stage == market_evidence.THREE_MINUTE_CONFIRMATION:
            return (
                f"{symbol}. LOOK NOW. Leader re-ignition. VWAP reclaimed and the 3 minute "
                "SuperTrend rung is confirmed. Attention only; entry is not authorized by this cue."
            )
        if stage == market_evidence.REIGNITION:
            return (
                f"{symbol}. LOOK NOW. Leader re-ignition. VWAP reclaimed with 30 second and "
                "1 minute SuperTrend bullish and active flow. 3 minute confirmation pending."
            )
    return ""


def _inherit_audio_wrapper(wrapper, wrapped) -> None:
    for name, value in getattr(wrapped, "__dict__", {}).items():
        if name.startswith("_gs") and not hasattr(wrapper, name):
            setattr(wrapper, name, value)


def install_leader_reset_audio() -> None:
    """Bind leader-reset audio at the historical GS477 audio position."""
    from mide import escalation
    from mide.authorities import market_evidence

    current = escalation.escalation_alert_phrase
    if getattr(current, _LEADER_RESET_AUDIO_OWNER, False):
        return

    @wraps(current)
    def alert_phrase(records: list[dict]) -> str:
        enriched = market_evidence.apply_leader_reset_marks(records)
        established = current(records)
        if established:
            return established
        return leader_reset_audio_phrase(enriched)

    _inherit_audio_wrapper(alert_phrase, current)
    alert_phrase._gs477_leader_reset_reignition = True
    alert_phrase._gs477_original = current
    setattr(alert_phrase, _LEADER_RESET_AUDIO_OWNER, True)
    escalation.escalation_alert_phrase = alert_phrase


__all__ = [
    "actionable_candidate_records",
    "install_pe_strength_order",
    "install_pe_strength_state",
    "state_with_pe_strength",
    "activate_operator_order_stage",
    "ordered_pe_strength_records",
    "pe_strength_score",
    "expansion_value",
    "participation_value",
    "ordered_fresh_event_records",
    "fresh_maturation_event",
    "ordered_rank_aware_records",
    "current_mission_rank",
    "ordered_state_contiguous_records",
    "attention_tiebreak",
    "strict_state_band",
    "ordered_state_first_records",
    "effective_operator_attention_band",
    "install_audio_architecture_gate_bridge",
    "install_maturation_transition_audio",
    "maturation_audio_phrase",
    "maturation_transition",
    "authoritative_gate_passed",
    "FRESH_3M_SECONDS",
    "augment_leader_reset_records",
    "data_integrity_markup",
    "decision_funnel_markup",
    "enrich_visible_records",
    "inject_css",
    "install_leader_reset_audio",
    "leader_reset_audio_phrase",
    "market_session_quality_markup",
    "mission_control_header_markup",
    "opportunity_card",
    "play_alert",
    "radar_table",
    "rejected_candidates_table",
    "rejection_diagnostics",
    "render_calibration_dashboard",
    "render_early_setups",
    "render_escalation_engine",
    "render_live_evidence_diagnostics",
    "render_live_opportunity_feed",
    "render_sidebar_audio_health",
    "render_walter_mission_control",
    "scanner_v2_dashboard_counts",
    "scanner_v2_display_sections",
]

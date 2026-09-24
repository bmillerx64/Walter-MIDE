"""Authoritative Walter Next Presentation + Audio boundary.

Presentation consumes authoritative evidence/state and renders or announces it. Legacy
UI functions are resolved dynamically so importing this authority during startup can
never freeze an older wrapper implementation.
"""

from __future__ import annotations

import html
from collections.abc import Callable, Iterable
from copy import deepcopy
from functools import wraps
from time import monotonic
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


# ---------------------------------------------------------------------------
# Base extraordinary-mover presentation
# ---------------------------------------------------------------------------
#
# GS333's original detector/selector/render responsibilities belong entirely to
# Presentation + Audio. The public gs333 module remains a compatibility facade so
# later historical installers can still replace its callables in the validated order.

EXTREME_MOVER_PCT = 75.0


def _extreme_number(
    record: dict,
    *keys: str,
    default: float | None = None,
) -> float | None:
    for key in keys:
        value = record.get(key)
        if value is None:
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return default


def _extreme_headline(record: dict) -> str:
    for key in ("headline", "catalyst_headline", "news_headline", "latest_headline"):
        value = str(record.get(key) or "").strip()
        if value:
            return value
    evidence = record.get("news_evidence") or record.get("catalyst_evidence") or {}
    if isinstance(evidence, dict):
        for key in ("headline", "title"):
            value = str(evidence.get(key) or "").strip()
            if value:
                return value
    return ""


def _extreme_attention(record: dict) -> tuple[str, ...]:
    try:
        from mide.gs309_current_attention_mission import current_attention_provenance

        return tuple(current_attention_provenance(record))
    except Exception:
        return ()


def _extreme_halted(record: dict) -> bool:
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


def base_extreme_market_event(record: dict) -> dict | None:
    """Describe an extraordinary attention event without granting trade authority."""
    pct_change = _extreme_number(record, "pct_change", default=0.0) or 0.0
    provenance = _extreme_attention(record)
    current = bool({"WEBULL_TOP_MOVER", "FRESH_NEWS_SEED"}.intersection(provenance))
    if pct_change < EXTREME_MOVER_PCT or not current:
        return None

    distance = _extreme_number(record, "vwap_distance_pct")
    relation = str(record.get("vwap_relation") or "").lower()
    trend = bool(record.get("supertrend_bullish") or record.get("supertrend_flip"))
    halted = _extreme_halted(record)
    headline = _extreme_headline(record)

    if halted:
        label = "HALTED · WATCH RESUME"
        guidance = (
            "Do not anticipate the reopen. Reassess fresh price, VWAP, trend, and "
            "volume after trading resumes."
        )
    elif distance is not None and distance > 5.0:
        label = "EXTREME MOVER · DO NOT CHASE"
        guidance = (
            "Major market event, not an entry signal. Wait for a constructive reset "
            "or halt/resume setup before reconsidering."
        )
    else:
        label = "EXTREME MOVER · LOOK NOW"
        guidance = (
            "Open the chart now, but require the normal entry evidence before "
            "considering a trade."
        )

    return {
        "symbol": str(record.get("symbol") or "").upper(),
        "pct_change": round(pct_change, 1),
        "vwap_distance_pct": None if distance is None else round(distance, 1),
        "vwap_relation": relation,
        "trend": trend,
        "halted": halted,
        "headline": headline,
        "provenance": provenance,
        "label": label,
        "guidance": guidance,
    }


def prioritized_extreme_event(
    records: Iterable[dict],
) -> tuple[dict | None, dict | None]:
    """Select the current extreme using the latest installed event semantics."""
    # Deliberately resolve through the compatibility module at call time. GS393,
    # GS465, and GS495 historically refine these public callables later in startup.
    from mide import gs333_extreme_mover_operator_priority as gs333

    choices: list[tuple[tuple, dict, dict]] = []
    for record in records or []:
        event = gs333.extreme_market_event(record)
        if not event:
            continue
        dollar_volume = _extreme_number(record, "dollar_volume", default=0.0) or 0.0
        choices.append(
            (
                (1 if event["halted"] else 0, event["pct_change"], dollar_volume),
                record,
                event,
            )
        )
    if not choices:
        return None, None
    _, record, event = max(choices, key=lambda item: item[0])
    return record, event


def extreme_event_markup(event: dict) -> str:
    distance = event.get("vwap_distance_pct")
    vwap = (
        "VWAP distance unavailable"
        if distance is None
        else f"{abs(float(distance)):.1f}% {'above' if float(distance) >= 0 else 'below'} VWAP"
    )
    trend = (
        "SuperTrend bullish"
        if event.get("trend")
        else "SuperTrend not confirmed"
    )
    headline = str(event.get("headline") or "").strip()
    catalyst = (
        f"<div class='small' style='margin-top:8px'><b>Catalyst:</b> "
        f"{html.escape(headline)}</div>"
        if headline
        else ""
    )
    return (
        "<div class='recommendation-box' style='--recommendation-color:#facc15'>"
        f"<div class='recommendation-label'>{html.escape(event['symbol'])} · "
        f"{html.escape(event['label'])}</div>"
        f"<div class='recommendation-message'>Current move: "
        f"+{float(event['pct_change']):.1f}% · {html.escape(vwap)} · "
        f"{html.escape(trend)}</div>"
        f"{catalyst}"
        f"<div class='small' style='margin-top:8px'><b>Walter:</b> "
        f"{html.escape(event['guidance'])}</div>"
        "</div>"
    )


def _in_streamlit_run() -> bool:
    try:
        from streamlit.runtime.scriptrunner import get_script_run_ctx

        return get_script_run_ctx(suppress_warning=True) is not None
    except Exception:
        return False


def install_base_extreme_presentation() -> None:
    """Bind GS333's historical action-first and maintenance-sidebar presentation."""
    from mide import ui

    if getattr(ui.render_walter_mission_control, "_gs333_operator_priority", False):
        return

    current_action = ui.render_walter_mission_control

    def render_action_first(records: list[dict]) -> None:
        if not _in_streamlit_run():
            return current_action(records)
        extreme_record, event = prioritized_extreme_event(records)
        if event is not None and extreme_record is not None:
            ui.st.markdown(extreme_event_markup(event), unsafe_allow_html=True)
            remaining = [record for record in records if record is not extreme_record]
            if remaining:
                current_action(remaining)
            return
        current_action(records)

    _inherit_audio_wrapper(render_action_first, current_action)
    render_action_first._gs333_operator_priority = True
    render_action_first._gs333_original = current_action
    ui.render_walter_mission_control = render_action_first

    import streamlit as st

    current_expander = st.expander
    if not getattr(current_expander, "_gs333_diagnostics_sidebar", False):
        diagnostic_labels = {"System Status", "Decision Funnel audit trails"}

        def diagnostic_expander(label, *args, **kwargs):
            if _in_streamlit_run() and str(label) in diagnostic_labels:
                return st.sidebar.expander(str(label), *args, **kwargs)
            return current_expander(label, *args, **kwargs)

        _inherit_audio_wrapper(diagnostic_expander, current_expander)
        diagnostic_expander._gs333_diagnostics_sidebar = True
        diagnostic_expander._gs333_original = current_expander
        st.expander = diagnostic_expander
        ui.st.expander = diagnostic_expander

    current_play_alert = ui.play_alert
    if not getattr(current_play_alert, "_gs333_voice_sidebar", False):
        def play_alert_in_sidebar(*args, **kwargs):
            if _in_streamlit_run():
                with st.sidebar.expander("Voice transport", expanded=False):
                    return current_play_alert(*args, **kwargs)
            return current_play_alert(*args, **kwargs)

        _inherit_audio_wrapper(play_alert_in_sidebar, current_play_alert)
        play_alert_in_sidebar._gs333_voice_sidebar = True
        play_alert_in_sidebar._gs333_original = current_play_alert
        ui.play_alert = play_alert_in_sidebar


EXTREME_DO_NOT_CHASE_TOP_TTL_SECONDS = 180.0
_extreme_first_seen: dict[str, float] = {}


def _actionable_operator_symbols(rows: list[dict]) -> set[str]:
    """Return symbols whose current state outranks an extended DO-NOT-CHASE banner."""
    from mide import gs310_unified_opportunity_state as unified

    priority_states = {
        unified.WATCH_FOR_ENTRY,
        unified.LOOK_NOW,
        unified.DEVELOPING,
    }
    symbols: set[str] = set()
    for record in rows:
        symbol = str(record.get("symbol") or "").strip().upper()
        if not symbol:
            continue
        try:
            state = unified.opportunity_state(record).get("state")
        except Exception:
            continue
        if state in priority_states:
            symbols.add(symbol)
    return symbols


def prioritized_extreme_with_decay(
    records,
    *,
    now: float | None = None,
) -> tuple[dict | None, dict | None]:
    """Apply GS393/GS439 action-first TTL behavior to current extreme events."""
    from mide import gs333_extreme_mover_operator_priority as extreme

    stamp = monotonic() if now is None else float(now)
    rows = list(records or [])
    actionable_symbols = _actionable_operator_symbols(rows)
    extreme_symbols: set[str] = set()
    choices: list[tuple[tuple, dict, dict]] = []

    for record in rows:
        event = extreme.extreme_market_event(record)
        if not event:
            continue
        symbol = str(event.get("symbol") or "").upper()
        if not symbol:
            continue
        extreme_symbols.add(symbol)
        _extreme_first_seen.setdefault(symbol, stamp)

        label = str(event.get("label") or "").upper()
        elapsed = max(0.0, stamp - _extreme_first_seen[symbol])
        competing_action = any(
            candidate_symbol != symbol for candidate_symbol in actionable_symbols
        )
        eligible = (
            "HALTED" in label
            or "LOOK NOW" in label
            or (
                not competing_action
                and elapsed <= EXTREME_DO_NOT_CHASE_TOP_TTL_SECONDS
            )
        )
        if not eligible:
            continue

        dollar_volume = _extreme_number(
            record,
            "dollar_volume",
            default=0.0,
        ) or 0.0
        choices.append(
            (
                (
                    1 if event.get("halted") else 0,
                    float(event.get("pct_change") or 0.0),
                    dollar_volume,
                ),
                record,
                event,
            )
        )

    for symbol in list(_extreme_first_seen):
        if symbol not in extreme_symbols:
            _extreme_first_seen.pop(symbol, None)

    if not choices:
        return None, None
    _, record, event = max(choices, key=lambda item: item[0])
    return record, event


def install_extreme_banner_decay() -> None:
    """Bind GS393/GS439 action-first extreme priority at its historical position."""
    from mide import gs333_extreme_mover_operator_priority as extreme

    current = extreme.prioritized_extreme_event
    if getattr(current, "_gs439_action_first_extreme", False):
        return

    def prioritized_with_decay(records, *, now: float | None = None):
        return prioritized_extreme_with_decay(records, now=now)

    prioritized_with_decay._gs393_extreme_decay = True
    prioritized_with_decay._gs439_action_first_extreme = True
    prioritized_with_decay._gs393_original = current
    extreme.prioritized_extreme_event = prioritized_with_decay


def reset_extreme_banner_decay_state() -> None:
    _extreme_first_seen.clear()


# ---------------------------------------------------------------------------
# Native market-event presentation
# ---------------------------------------------------------------------------

_LATEST_ACTIONABLE_SYMBOLS: set[str] = set()
_MARKET_EVENT_MISSION_OWNER = "_walter_gs334_market_event_symbols"
_MARKET_EVENT_HEADER_OWNER = "_walter_gs334_market_event_lane"


def visible_market_events(
    events: Iterable[dict] | None,
    actionable_symbols: Iterable[str] | None,
) -> list[dict]:
    """Suppress market-awareness rows already represented by current trade records."""
    active = {
        str(symbol or "").strip().upper()
        for symbol in actionable_symbols or []
    }
    return [
        dict(event)
        for event in events or []
        if str(event.get("symbol") or "").strip().upper() not in active
    ]


def market_event_markup(
    events: Iterable[dict] | None,
    actionable_symbols: Iterable[str] | None = None,
) -> str:
    """Render the established attention-only native market-events strip."""
    visible = visible_market_events(events, actionable_symbols)
    if not visible:
        return ""

    chips = "".join(
        (
            "<span style='display:inline-block;margin:3px 8px 3px 0;padding:5px 9px;"
            "border:1px solid #f59e0b;border-radius:8px;background:#111827;'>"
            f"<b>{html.escape(str(event['symbol']))}</b> "
            f"<span style='color:#fbbf24'>+{float(event['pct_change']):.1f}%</span> "
            f"<span style='color:#94a3b8'>#{int(event['rank'])} Webull</span></span>"
        )
        for event in visible
    )
    return (
        "<div style='margin:10px 0 14px 0;padding:10px 14px;border:1px solid #92400e;"
        "border-left:4px solid #f59e0b;border-radius:10px;background:#0b111b;'>"
        "<div style='font-weight:800;letter-spacing:.06em;color:#fbbf24'>"
        "⚡ LIVE MARKET EVENTS · ATTENTION ONLY</div>"
        f"<div style='margin-top:5px'>{chips}</div>"
        "<div style='margin-top:4px;color:#94a3b8;font-size:.86rem'>"
        "Extraordinary current movers outside Walter's trade-qualified results. "
        "Open the chart if useful; normal entry gates still apply.</div></div>"
    )


def _streamlit_completed_scan_market_events() -> list[dict]:
    try:
        import streamlit as st
        from mide.authorities import market_evidence

        return market_evidence.completed_scan_market_events(st.session_state)
    except Exception:
        return []


def install_market_event_presentation() -> None:
    """Bind GS334's current-symbol tracking and header strip at its historical point."""
    from mide import ui
    from mide.authorities import market_evidence

    current_mission = ui.walter_mission_control
    if not getattr(current_mission, _MARKET_EVENT_MISSION_OWNER, False):
        @wraps(current_mission)
        def mission_with_current_symbols(records: list[dict]) -> dict:
            _LATEST_ACTIONABLE_SYMBOLS.clear()
            _LATEST_ACTIONABLE_SYMBOLS.update(
                str(record.get("symbol") or "").strip().upper()
                for record in records or []
                if str(record.get("symbol") or "").strip()
            )
            return current_mission(records)

        _inherit_audio_wrapper(mission_with_current_symbols, current_mission)
        mission_with_current_symbols._gs334_market_event_symbols = True
        mission_with_current_symbols._gs334_original = current_mission
        setattr(
            mission_with_current_symbols,
            _MARKET_EVENT_MISSION_OWNER,
            True,
        )
        ui.walter_mission_control = mission_with_current_symbols

    current_header = ui.mission_control_header_markup
    if not getattr(current_header, _MARKET_EVENT_HEADER_OWNER, False):
        @wraps(current_header)
        def header_with_market_events(*args, **kwargs):
            markup = current_header(*args, **kwargs)
            if not _in_streamlit_run():
                return markup
            persisted = _streamlit_completed_scan_market_events()
            events = (
                persisted
                if persisted
                else market_evidence._LATEST_MARKET_EVENTS
            )
            return markup + market_event_markup(
                events,
                _LATEST_ACTIONABLE_SYMBOLS,
            )

        _inherit_audio_wrapper(header_with_market_events, current_header)
        header_with_market_events._gs334_market_event_lane = True
        header_with_market_events._gs335_persistent_market_events = True
        header_with_market_events._gs334_original = current_header
        setattr(header_with_market_events, _MARKET_EVENT_HEADER_OWNER, True)
        ui.mission_control_header_markup = header_with_market_events


# ---------------------------------------------------------------------------
# Market-leader continuity presentation
# ---------------------------------------------------------------------------

MAJOR_MOVER_PCT = 20.0
MIN_DOLLAR_VOLUME = 250_000.0
LEADER_DOMINANCE = 78.0
_MARKET_LEADER_CONTINUITY_OWNER = "_walter_gs443_market_leader_radar_continuity"


def _market_leader_number(
    record: dict,
    *keys: str,
    default: float | None = None,
) -> float | None:
    for key in keys:
        value = record.get(key)
        if value is None:
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return default


def _focused_mission_symbols(mission: dict | None) -> set[str]:
    symbols: set[str] = set()
    if not isinstance(mission, dict):
        return symbols
    for key in ("primary", "secondary"):
        item = mission.get(key)
        if not isinstance(item, dict):
            continue
        record = item.get("record")
        if isinstance(record, dict):
            symbol = str(record.get("symbol") or "").strip().upper()
            if symbol:
                symbols.add(symbol)
    return symbols


def market_leader_candidate(
    records: Iterable[dict],
    *,
    mission: dict | None = None,
) -> tuple[dict | None, dict | None]:
    """Return one uncovered current leader for watch-only continuity."""
    from mide.gs305_second_wave_attention import attention_evaluation
    from mide.gs309_current_attention_mission import current_attention_provenance
    from mide.gs333_extreme_mover_operator_priority import prioritized_extreme_event

    rows = list(records or [])
    focused = _focused_mission_symbols(mission)
    displayed_extreme, _event = prioritized_extreme_event(rows)
    displayed_extreme_symbol = (
        str(displayed_extreme.get("symbol") or "").strip().upper()
        if isinstance(displayed_extreme, dict)
        else ""
    )
    choices: list[tuple[tuple[float, float, float], dict, dict]] = []

    for record in rows:
        symbol = str(record.get("symbol") or "").strip().upper()
        if not symbol or symbol in focused or symbol == displayed_extreme_symbol:
            continue

        provenance = tuple(current_attention_provenance(record))
        if "WEBULL_TOP_MOVER" not in provenance:
            continue

        pct_change = _market_leader_number(record, "pct_change", default=0.0) or 0.0
        dollar_volume = (
            _market_leader_number(record, "dollar_volume", default=0.0) or 0.0
        )
        dominance = (
            _market_leader_number(
                record,
                "market_dominance_score",
                default=0.0,
            )
            or 0.0
        )
        if pct_change < MAJOR_MOVER_PCT:
            continue
        if dollar_volume < MIN_DOLLAR_VOLUME:
            continue
        if dominance < LEADER_DOMINANCE:
            continue

        existing_attention = attention_evaluation(record)
        if existing_attention.get("eligible"):
            continue

        distance = _market_leader_number(record, "vwap_distance_pct")
        relation = str(record.get("vwap_relation") or "").strip().lower()
        alignment = int(
            _market_leader_number(record, "alignment_score", default=0.0) or 0
        )

        if distance is not None and distance > 5.0:
            state = "WAIT FOR RESET"
            guidance = (
                "Dominant current mover, but extended above VWAP. Keep the chart "
                "available; do not chase. Reassess only after a constructive reset."
            )
        elif relation != "above" or alignment < 2:
            state = "STRUCTURE NOT READY"
            guidance = (
                "Dominant current mover with incomplete structure. Keep it on radar "
                "while 30s → 1m → 3m alignment develops; normal qualification remains closed."
            )
        else:
            state = "TRACK RE-IGNITION"
            guidance = (
                "Dominant current mover returning toward workable structure. Keep it "
                "visible; normal qualification still decides whether any trade is justified."
            )

        event = {
            "symbol": symbol,
            "state": state,
            "pct_change": round(pct_change, 1),
            "dollar_volume": round(dollar_volume, 0),
            "dominance": round(dominance, 1),
            "vwap_distance_pct": None if distance is None else round(distance, 1),
            "alignment_score": alignment,
            "guidance": guidance,
            "provenance": provenance,
        }
        choices.append(((dominance, pct_change, dollar_volume), record, event))

    if not choices:
        return None, None
    _, record, event = max(choices, key=lambda item: item[0])
    return record, event


def market_leader_markup(event: dict) -> str:
    """Render GS443's watch-only continuity strip."""
    distance = event.get("vwap_distance_pct")
    vwap_text = (
        "VWAP distance unavailable"
        if distance is None
        else f"{abs(float(distance)):.1f}% {'above' if float(distance) >= 0 else 'below'} VWAP"
    )
    return (
        "<div style='background:#0b1119;border:1px solid #36566f;border-radius:12px;"
        "margin:8px 0 14px;padding:10px 12px'>"
        "<div style='font-size:.76rem;letter-spacing:.09em;font-weight:950;color:#7dd3fc'>"
        "MARKET LEADER RADAR · WATCH ONLY · NO ENTRY AUTHORITY</div>"
        f"<div style='margin-top:5px;font-weight:900;color:#e6f4ff'>{html.escape(str(event['symbol']))}"
        f" · {html.escape(str(event['state']))}</div>"
        f"<div style='color:#c7d7e5;font-size:.86rem;margin-top:3px'>"
        f"Move +{float(event['pct_change']):.1f}% · Dominance {float(event['dominance']):.1f}/100 · "
        f"Alignment {int(event['alignment_score'])}/3 · {html.escape(vwap_text)}</div>"
        f"<div style='color:#93a4b8;font-size:.81rem;margin-top:5px'>{html.escape(str(event['guidance']))}</div>"
        "</div>"
    )


def install_market_leader_continuity() -> None:
    """Bind GS443 at its historical presentation position."""
    from mide import ui

    current = ui.render_walter_mission_control
    if getattr(current, _MARKET_LEADER_CONTINUITY_OWNER, False):
        return

    def render_walter_mission_control(records: list[dict]) -> None:
        result = current(records)
        if not _in_streamlit_run():
            return result
        mission = ui.walter_mission_control(records)
        _record, event = market_leader_candidate(records, mission=mission)
        if event is not None:
            ui.st.markdown(market_leader_markup(event), unsafe_allow_html=True)
        return result

    _inherit_audio_wrapper(render_walter_mission_control, current)
    render_walter_mission_control._gs443_market_leader_radar_continuity = True
    render_walter_mission_control._gs443_original = current
    setattr(
        render_walter_mission_control,
        _MARKET_LEADER_CONTINUITY_OWNER,
        True,
    )
    ui.render_walter_mission_control = render_walter_mission_control


# ---------------------------------------------------------------------------
# Authoritative extreme-mover presentation semantics
# ---------------------------------------------------------------------------
#
# GS333 remains the base extraordinary-event detector for now. GS465 and GS495 no
# longer stack wrappers around it: one Presentation + Audio wrapper owns their staged
# semantic corrections, while GS466's awareness-only stale-bar exception also lives
# here.

ANTI_CHASE_VWAP_DISTANCE_PCT = 2.0
_EXTREME_EVENT_OWNER = "_walter_next_extreme_event_semantics_owner"
_EXTREME_SELECTION_OWNER = "_walter_next_extreme_selection_continuity_owner"
_EXTREME_AWARENESS_REASON_OWNER = "_walter_gs466_extreme_awareness_reason_owner"
_EXTREME_AWARENESS_VISIBLE_OWNER = "_walter_gs466_extreme_awareness_visible_owner"


def _specific_extreme_look_now(view: dict) -> bool:
    from mide import gs310_unified_opportunity_state as unified

    if str(view.get("state") or "") != unified.LOOK_NOW:
        return False
    reason = str(view.get("reason") or "").strip().lower()
    generic = (
        "a current attention trigger says this symbol deserves a chart review",
        "current market-attention leader",
    )
    return bool(reason and not any(text in reason for text in generic))


def _cleaned_extreme_value(event: dict | None, record: dict) -> dict | None:
    """Apply GS465 truthful-label semantics to an already-detected extreme event."""
    if not event:
        return event
    if event.get("halted") or "DO NOT CHASE" in str(event.get("label") or "").upper():
        return event

    from mide import gs310_unified_opportunity_state as unified

    try:
        view = unified.opportunity_state(record)
    except Exception:
        view = {}
    state = str(view.get("state") or "")

    cleaned = dict(event)
    if state == unified.WATCH_FOR_ENTRY:
        cleaned["label"] = "EXTREME MOVER · WATCH FOR ENTRY"
        cleaned["guidance"] = (
            "The normal opportunity state has earned WATCH FOR ENTRY. Use the same "
            "entry evidence and risk discipline as any other setup."
        )
    elif _specific_extreme_look_now(view):
        cleaned["label"] = "EXTREME MOVER · LOOK NOW"
        cleaned["guidance"] = (
            "Current structure independently earned LOOK NOW; the large percentage "
            "move is context, not the reason for urgency."
        )
    else:
        cleaned["label"] = "EXTREME MOVER · WATCH"
        cleaned["guidance"] = (
            "Major mover worth monitoring, but the current structure has not earned "
            "LOOK NOW. Let normal VWAP/ST/ignition evidence promote it."
        )
    return cleaned


def cleaned_extreme_event(original, record: dict) -> dict | None:
    """Compatibility helper preserving GS465's original callable contract."""
    return _cleaned_extreme_value(original(record), record)


def _anti_chase_extreme_value(event: dict | None) -> dict | None:
    """Apply GS495's <=2% VWAP working-zone qualifier to a final extreme event."""
    if not isinstance(event, dict):
        return event
    label = str(event.get("label") or "").upper()
    if event.get("halted") or "DO NOT CHASE" in label:
        return event

    try:
        distance = float(event.get("vwap_distance_pct"))
    except (TypeError, ValueError):
        distance = None

    if (
        distance is None
        or distance <= ANTI_CHASE_VWAP_DISTANCE_PCT
        or "LOOK NOW" not in label
    ):
        return event

    view = deepcopy(event)
    view["label"] = "EXTREME MOVER · LOOK NOW · EXTENDED / WATCH RESET"
    view["guidance"] = (
        "Urgent attention only. Price is outside Walter's <=2% VWAP working zone; "
        "do not chase. Keep the chart visible and wait for a constructive reset "
        "toward VWAP before reconsidering."
    )
    view["anti_chase_active"] = True
    view["entry_authority_changed"] = False
    return view


def truthful_extreme_market_event(original, record: dict) -> dict | None:
    """Compatibility helper preserving GS495's original callable contract."""
    return _anti_chase_extreme_value(original(record))


def activate_extreme_event_stage(stage: str) -> None:
    """Activate GS465/GS495 meaning inside one authoritative extreme-event wrapper."""
    if stage not in {"cleanup", "anti_chase"}:
        raise ValueError(f"unknown extreme-event stage: {stage}")

    from mide import gs333_extreme_mover_operator_priority as gs333

    current = gs333.extreme_market_event
    if getattr(current, _EXTREME_EVENT_OWNER, False):
        wrapper = current
    else:
        baseline = current

        @wraps(baseline)
        def extreme_market_event(record: dict) -> dict | None:
            event = baseline(record)
            active = set(
                getattr(
                    extreme_market_event,
                    "_walter_next_extreme_event_stages",
                    set(),
                )
            )
            if "cleanup" in active:
                event = _cleaned_extreme_value(event, record)
            if "anti_chase" in active:
                event = _anti_chase_extreme_value(event)
            return event

        _inherit_audio_wrapper(extreme_market_event, baseline)
        setattr(extreme_market_event, _EXTREME_EVENT_OWNER, True)
        extreme_market_event._walter_next_extreme_event_stages = set()
        extreme_market_event._walter_next_extreme_event_baseline = baseline
        gs333.extreme_market_event = extreme_market_event
        wrapper = extreme_market_event

    active = set(getattr(wrapper, "_walter_next_extreme_event_stages", set()))
    active.add(stage)
    wrapper._walter_next_extreme_event_stages = active

    if stage == "cleanup":
        wrapper._gs465_presentation_priority_cleanup = True
        if not hasattr(wrapper, "_gs465_original"):
            wrapper._gs465_original = getattr(
                wrapper, "_walter_next_extreme_event_baseline", None
            )
    else:
        wrapper._gs495_extreme_attention_anti_chase_semantics = True
        if not hasattr(wrapper, "_gs495_original"):
            wrapper._gs495_original = getattr(
                wrapper, "_walter_next_extreme_event_baseline", None
            )


def _non_extreme_actionable_symbols(
    rows: list[dict],
    extreme_symbols: set[str],
) -> set[str]:
    from mide import gs310_unified_opportunity_state as unified

    priority_states = {
        unified.WATCH_FOR_ENTRY,
        unified.LOOK_NOW,
        unified.DEVELOPING,
    }
    symbols: set[str] = set()
    for record in rows:
        symbol = str(record.get("symbol") or "").strip().upper()
        if not symbol or symbol in extreme_symbols:
            continue
        try:
            state = str(unified.opportunity_state(record).get("state") or "")
        except Exception:
            continue
        if state in priority_states:
            symbols.add(symbol)
    return symbols


def prioritized_extreme_with_watch_continuity(original, records, *, now=None):
    """Preserve GS465's generic extreme-WATCH single-banner continuity."""
    from mide import gs333_extreme_mover_operator_priority as extreme

    rows = list(records or [])
    if now is None:
        selected = original(rows)
    else:
        try:
            selected = original(rows, now=now)
        except TypeError:
            selected = original(rows)
    if selected and selected[0] is not None:
        return selected

    events: list[tuple[dict, dict]] = []
    extreme_symbols: set[str] = set()
    for record in rows:
        event = extreme.extreme_market_event(record)
        if not event:
            continue
        symbol = str(event.get("symbol") or record.get("symbol") or "").strip().upper()
        if symbol:
            extreme_symbols.add(symbol)
        events.append((record, event))

    if _non_extreme_actionable_symbols(rows, extreme_symbols):
        return None, None

    choices: list[tuple[tuple[float, float], dict, dict]] = []
    for record, event in events:
        if str(event.get("label") or "").upper() != "EXTREME MOVER · WATCH":
            continue
        try:
            pct_change = float(event.get("pct_change") or 0.0)
        except (TypeError, ValueError):
            pct_change = 0.0
        try:
            dollar_volume = float(record.get("dollar_volume") or 0.0)
        except (TypeError, ValueError):
            dollar_volume = 0.0
        choices.append(((pct_change, dollar_volume), record, event))

    if not choices:
        return None, None
    _, record, event = max(choices, key=lambda item: item[0])
    return record, event


def install_extreme_selection_continuity() -> None:
    """Bind GS465's selection fallback once at its historical install point."""
    from mide import gs333_extreme_mover_operator_priority as gs333

    current = gs333.prioritized_extreme_event
    if getattr(current, _EXTREME_SELECTION_OWNER, False):
        return

    @wraps(current)
    def prioritized_extreme_event(records, *, now=None):
        return prioritized_extreme_with_watch_continuity(current, records, now=now)

    _inherit_audio_wrapper(prioritized_extreme_event, current)
    prioritized_extreme_event._gs465_presentation_priority_cleanup = True
    prioritized_extreme_event._gs465_original = current
    setattr(prioritized_extreme_event, _EXTREME_SELECTION_OWNER, True)
    gs333.prioritized_extreme_event = prioritized_extreme_event


def _source_bar_stale_reason(reason: str) -> bool:
    return str(reason or "").strip().lower().startswith("source bar is ")


def extreme_awareness_continuity(record: dict, *, base_reason: str) -> bool:
    """Keep a current extreme mover visible when only its source-bar age is stale."""
    if not _source_bar_stale_reason(base_reason):
        return False
    try:
        from mide.gs333_extreme_mover_operator_priority import extreme_market_event

        return extreme_market_event(record) is not None
    except Exception:
        return False


def install_extreme_awareness_continuity() -> None:
    """Bind GS466's awareness-only stale-bar exception at its historical position."""
    from mide import gs373_operator_visibility_freshness as freshness

    current_reason = freshness.operator_visibility_reason
    if not getattr(current_reason, _EXTREME_AWARENESS_REASON_OWNER, False):
        original_reason = current_reason

        def operator_visibility_reason(record: dict) -> str:
            reason = original_reason(record)
            if extreme_awareness_continuity(record, base_reason=reason):
                return ""
            return reason

        operator_visibility_reason._gs466_extreme_awareness_continuity = True
        operator_visibility_reason._gs466_original = original_reason
        setattr(
            operator_visibility_reason,
            _EXTREME_AWARENESS_REASON_OWNER,
            True,
        )
        freshness.operator_visibility_reason = operator_visibility_reason

    current_visible = freshness.operator_visible
    if not getattr(current_visible, _EXTREME_AWARENESS_VISIBLE_OWNER, False):
        def operator_visible(record: dict) -> bool:
            return not freshness.operator_visibility_reason(record)

        operator_visible._gs466_extreme_awareness_continuity = True
        operator_visible._gs466_original = current_visible
        setattr(operator_visible, _EXTREME_AWARENESS_VISIBLE_OWNER, True)
        freshness.operator_visible = operator_visible


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


# ---------------------------------------------------------------------------
# GS480 catalyst-story presentation facts
# ---------------------------------------------------------------------------

_CATALYST_STORY_OWNER = "_walter_gs480_story_why_owner"


def catalyst_story_display_facts(record: dict) -> list[str]:
    """Render bounded story facts from authoritative news evidence only."""
    context = record.get("catalyst_story") or {}
    categories = list(context.get("categories") or [])
    quantities = list(context.get("quantities") or [])
    facts: list[str] = []
    if categories:
        readable = [category.replace("_", " ").title() for category in categories[:3]]
        facts.append("Story: " + " · ".join(readable))
    role_facts: list[str] = []
    for item in quantities:
        role = str(item.get("role") or "")
        if role in {
            "DEAL_OR_BACKLOG",
            "REVENUE",
            "INVESTMENT_OR_FUNDING",
            "DILUTION_OR_FINANCING",
        }:
            role_facts.append(
                f"{item.get('text')} {role.replace('_', ' ').lower()}"
            )
        if len(role_facts) >= 3:
            break
    if role_facts:
        facts.append(" · ".join(role_facts))
    return facts


def install_catalyst_story_presentation() -> None:
    """Install GS480 story facts inside Presentation + Audio ownership."""
    from mide import ui

    current = ui._why_sections
    if getattr(current, _CATALYST_STORY_OWNER, False):
        return

    @wraps(current)
    def why_sections(record):
        sections = dict(current(record))
        facts = catalyst_story_display_facts(record)
        if facts:
            existing = str(sections.get("Catalyst") or "").strip()
            addition = " · ".join(facts)
            if addition not in existing:
                sections["Catalyst"] = (
                    f"{existing} · {addition}" if existing else addition
                )
        return sections

    _inherit_audio_wrapper(why_sections, current)
    setattr(why_sections, _CATALYST_STORY_OWNER, True)
    why_sections._gs480_original = current
    ui._why_sections = why_sections


# ---------------------------------------------------------------------------
# GS503 catalyst/company-scale operator presentation
# ---------------------------------------------------------------------------

_CATALYST_SCALE_WHY_OWNER = "_walter_gs503_scale_why_owner"


def catalyst_company_scale_display_summary(record: dict) -> str:
    """Return the bounded factual company-scale summary for operator display."""
    detail = record.get("catalyst_company_scale") or {}
    return str(detail.get("summary") or "").strip()


def install_catalyst_company_scale_presentation() -> None:
    """Append GS503 relative-scale facts to the Catalyst presentation section."""
    from mide import ui

    current = ui._why_sections
    if getattr(current, _CATALYST_SCALE_WHY_OWNER, False):
        return

    @wraps(current)
    def why_sections_with_company_scale(record):
        sections = dict(current(record))
        summary = catalyst_company_scale_display_summary(record)
        if summary:
            existing = str(sections.get("Catalyst") or "").strip()
            if summary not in existing:
                sections["Catalyst"] = (
                    f"{existing} · {summary}" if existing else summary
                )
        return sections

    _inherit_audio_wrapper(why_sections_with_company_scale, current)
    setattr(
        why_sections_with_company_scale,
        _CATALYST_SCALE_WHY_OWNER,
        True,
    )
    why_sections_with_company_scale._gs503_catalyst_company_scale = True
    why_sections_with_company_scale._gs503_original = current
    ui._why_sections = why_sections_with_company_scale


# ---------------------------------------------------------------------------
# GS511 Entry Window VWAP presentation truth
# ---------------------------------------------------------------------------

ENTRY_WINDOW_NEAR_VWAP_MAX_PCT = 2.0
_ENTRY_WINDOW_VWAP_OWNER = "_walter_gs511_entry_window_vwap_truth"


def _entry_window_number(record: dict, key: str) -> float | None:
    value = record.get(key)
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def entry_window_near_vwap(record: dict) -> bool:
    """Return the established presentation-safe near-VWAP condition."""
    relation = str(record.get("vwap_relation") or "").strip().lower()
    distance = _entry_window_number(record, "vwap_distance_pct")
    return relation == "above" and (
        distance is None or distance <= ENTRY_WINDOW_NEAR_VWAP_MAX_PCT
    )


def install_entry_window_vwap_truth() -> None:
    """Keep Entry Window display/feed truth inside Walter's established VWAP zone."""
    from mide import escalation
    from mide import live_opportunity_feed

    current_state = escalation.escalation_state
    if getattr(current_state, _ENTRY_WINDOW_VWAP_OWNER, False):
        # Warm Streamlit reruns can retain the feed module's imported snapshot
        # binding even when escalation already owns this presentation correction.
        live_opportunity_feed.escalation_snapshot = escalation.escalation_snapshot
        return

    current_snapshot = escalation.escalation_snapshot

    @wraps(current_state)
    def escalation_state(record: dict) -> str:
        existing = current_state(record)
        if existing != escalation.ENTRY_WINDOW_OPEN:
            return existing
        if entry_window_near_vwap(record):
            return existing

        distance = _entry_window_number(record, "vwap_distance_pct")
        if distance is not None and distance > 5.0:
            return escalation.TOO_EXTENDED

        relation = str(record.get("vwap_relation") or "").strip().lower()
        trend = bool(
            record.get("supertrend_bullish") or record.get("supertrend_flip")
        )
        if relation == "above" and trend:
            return escalation.WATCH_CLOSELY
        return escalation.MONITOR

    @wraps(current_snapshot)
    def escalation_snapshot(record: dict) -> dict:
        snapshot = dict(current_snapshot(record))
        snapshot["state"] = escalation_state(record)
        return snapshot

    setattr(escalation_state, _ENTRY_WINDOW_VWAP_OWNER, True)
    setattr(escalation_snapshot, _ENTRY_WINDOW_VWAP_OWNER, True)
    escalation_state._gs511_original = current_state
    escalation_snapshot._gs511_original = current_snapshot

    escalation.escalation_state = escalation_state
    escalation.escalation_snapshot = escalation_snapshot
    live_opportunity_feed.escalation_snapshot = escalation_snapshot


# ---------------------------------------------------------------------------
# GS414/GS436 final enriched Opportunity render boundary
# ---------------------------------------------------------------------------

FINAL_ORDER_OWNER_ATTR = "_walter_final_enriched_opportunity_order_owner"


def final_enriched_opportunity_records(
    records: list[dict],
    *,
    actionable_function=None,
) -> list[dict]:
    """Build the complete enriched presentation collection, then sort it once."""
    from mide import ui
    from mide.gs369_escalation_priority_order import ordered_escalation_records
    from mide.gs477_leader_reset_reignition import enrich_visible_records

    actionable = actionable_function or ui.actionable_candidate_records
    enriched = enrich_visible_records(list(records or []), actionable)
    return ordered_escalation_records(enriched)


def bind_final_enriched_opportunity_order(
    attr: str,
    *,
    show_legend: bool = False,
) -> None:
    """Freeze final enrichment/order across one public Opportunity renderer."""
    from mide import ui

    current = getattr(ui, attr)
    if getattr(current, FINAL_ORDER_OWNER_ATTR, False):
        return

    def render_with_final_enriched_order(records: list[dict]) -> None:
        public_actionable = ui.actionable_candidate_records
        ordered = final_enriched_opportunity_records(
            records,
            actionable_function=public_actionable,
        )

        def frozen_actionable(_records: list[dict]) -> list[dict]:
            return list(ordered)

        _inherit_audio_wrapper(frozen_actionable, public_actionable)
        ui.actionable_candidate_records = frozen_actionable
        try:
            if show_legend:
                ui.st.caption(
                    "Order: P/E Strength (Participation + Expansion) descending. "
                    "Color = structural state, not score."
                )
            return current(list(ordered))
        finally:
            ui.actionable_candidate_records = public_actionable

    _inherit_audio_wrapper(render_with_final_enriched_order, current)
    render_with_final_enriched_order._gs414_final_enriched_opportunity_order = True
    render_with_final_enriched_order._gs436_final_render_hard_bind = True
    render_with_final_enriched_order._gs539_live_path_hard_bind = True
    render_with_final_enriched_order._gs414_original = current
    setattr(render_with_final_enriched_order, FINAL_ORDER_OWNER_ATTR, True)
    setattr(ui, attr, render_with_final_enriched_order)


# ---------------------------------------------------------------------------
# GS479 headline catalyst magnitude presentation
# ---------------------------------------------------------------------------

_HEADLINE_MAGNITUDE_WHY_OWNER = "_walter_gs479_headline_magnitude_why_owner"


def headline_catalyst_magnitude_display_summary(record: dict) -> str:
    """Return the factual GS479 headline-scale summary for Catalyst display."""
    detail = record.get("catalyst_magnitude") or {}
    return str(detail.get("summary") or "").strip()


def install_headline_catalyst_magnitude_presentation() -> None:
    """Append GS479 factual magnitude context to the Catalyst display section."""
    from mide import ui

    current = ui._why_sections
    if getattr(current, _HEADLINE_MAGNITUDE_WHY_OWNER, False):
        return

    @wraps(current)
    def why_sections_with_magnitude(record: dict):
        sections = dict(current(record))
        summary = headline_catalyst_magnitude_display_summary(record)
        if summary:
            existing = str(sections.get("Catalyst") or "").strip()
            if summary not in existing:
                sections["Catalyst"] = (
                    f"{existing} · {summary}" if existing else summary
                )
        return sections

    _inherit_audio_wrapper(why_sections_with_magnitude, current)
    why_sections_with_magnitude._gs479_headline_catalyst_magnitude = True
    why_sections_with_magnitude._gs479_original = current
    setattr(
        why_sections_with_magnitude,
        _HEADLINE_MAGNITUDE_WHY_OWNER,
        True,
    )
    ui._why_sections = why_sections_with_magnitude


__all__ = [
    "install_headline_catalyst_magnitude_presentation",
    "headline_catalyst_magnitude_display_summary",
    "bind_final_enriched_opportunity_order",
    "final_enriched_opportunity_records",
    "FINAL_ORDER_OWNER_ATTR",
    "install_entry_window_vwap_truth",
    "entry_window_near_vwap",
    "ENTRY_WINDOW_NEAR_VWAP_MAX_PCT",
    "install_catalyst_company_scale_presentation",
    "catalyst_company_scale_display_summary",
    "install_catalyst_story_presentation",
    "catalyst_story_display_facts",
    "actionable_candidate_records",
    "install_market_event_presentation",
    "market_event_markup",
    "visible_market_events",
    "_LATEST_ACTIONABLE_SYMBOLS",
    "install_market_leader_continuity",
    "market_leader_markup",
    "market_leader_candidate",
    "LEADER_DOMINANCE",
    "MIN_DOLLAR_VOLUME",
    "MAJOR_MOVER_PCT",
    "reset_extreme_banner_decay_state",
    "install_extreme_banner_decay",
    "prioritized_extreme_with_decay",
    "EXTREME_DO_NOT_CHASE_TOP_TTL_SECONDS",
    "install_base_extreme_presentation",
    "extreme_event_markup",
    "prioritized_extreme_event",
    "base_extreme_market_event",
    "EXTREME_MOVER_PCT",
    "install_extreme_awareness_continuity",
    "extreme_awareness_continuity",
    "install_extreme_selection_continuity",
    "prioritized_extreme_with_watch_continuity",
    "activate_extreme_event_stage",
    "truthful_extreme_market_event",
    "cleaned_extreme_event",
    "ANTI_CHASE_VWAP_DISTANCE_PCT",
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

"""GS310: one display-only opportunity state for Walter's trader-facing surfaces.

The scanner remains the source of truth for discovery, qualification, ranking,
readiness, thresholds, and execution. This module only translates the current
record into one concise trader-facing state so Mission and Recommendation do not
independently describe the same symbol as EARLY, ENTRY WINDOW, WATCH, and NO TRADE.
"""
from __future__ import annotations

from copy import deepcopy
import html

from .authorities.thesis_state import (
    CHASE_WAIT,
    DEVELOPING,
    HALTED,
    LOOK_NOW,
    STATE_COLORS,
    WATCH_FOR_ENTRY,
    _attention,
    _expansion,
    _halted,
    _number,
    _participation,
    base_opportunity_state as opportunity_state,
)


def look_now_context(record: dict, view: dict) -> str:
    """Explain why LOOK NOW owns attention without changing the state itself."""
    if str(view.get("state") or "") != LOOK_NOW:
        return ""
    if record.get("reference_data_blocked_awareness"):
        return "REFERENCE DATA BLOCKED"
    if record.get("operator_reset_retest_look_now"):
        return "RESET / RETEST"

    reason = str(view.get("reason") or "").upper()
    try:
        from .gs455_early_ignition_3m_confirmation import progression_signal

        if progression_signal(record).get("active"):
            return "STRUCTURE MATURING"
    except Exception:
        pass
    if any(token in reason for token in (
        "EARLY IGNITION",
        "BOTTOM-UP",
        "ST/VWAP",
        "RE-IGNITION",
    )):
        return "STRUCTURE MATURING"
    return "MARKET ATTENTION"



def _confidence_cue(item: dict) -> str:
    """Keep the familiar meter cue without creating a second opportunity state."""
    confidence = int(item.get("confidence", 0) or 0)
    if confidence >= 75:
        return "🟡 BUILDING"
    if confidence >= 60:
        return "🔵 WATCH"
    return "🔵 EARLY"


def _secondary_gap(record: dict) -> str:
    """Return one concise reason the secondary is not the primary focus."""
    distance = _number(record, "vwap_distance_pct") or 0.0
    participation, _ = _participation(record)
    relation = str(record.get("vwap_relation") or "").lower()
    if distance > 2.0:
        return "Slightly extended."
    if relation != "above":
        return "Waiting for VWAP reclaim."
    if participation is None or participation < 90.0:
        return "Needs stronger participation."
    return "Lower current priority than the primary opportunity."


def _target_markup(item: dict, role: str, primary: dict | None = None) -> str:
    """Render the unified state while preserving Walter's established mission cues."""
    from . import ui

    record = item["record"]
    view = opportunity_state(record)
    confidence = int(item.get("confidence", 0) or 0)
    cue = _confidence_cue(item)
    previous = item.get("previous_record") or {}

    conditions = list(item.get("conditions") or [])
    remaining = sum(not condition.get("passed") for condition in conditions)
    window = "Now" if remaining == 0 else ("2–5 minutes" if remaining == 1 else "5–15 minutes")
    checklist = "".join(
        f"<div class='mission-check'>{index}. {'✓' if condition.get('passed') else '□'} "
        f"{html.escape(str(condition.get('label') or ''))}</div>"
        for index, condition in enumerate(conditions, start=1)
    )
    reasons = "".join(
        f"<div class='mission-reason'>✓ {html.escape(str(reason))}</div>"
        for reason in list(item.get("reasons") or [])[:3]
    )
    if not reasons:
        reasons = "<div class='mission-reason'>✓ Current ranked observation</div>"

    previous_confidence = ui.hot_list_priority_score(previous) if previous else confidence
    delta = confidence - previous_confidence
    direction = "▲" if delta >= 0 else "▼"
    delta_class = "meter-delta-up" if delta >= 0 else "meter-delta-down"

    just_opened = bool(
        item.get("band") == "trade_soon"
        and previous
        and not (
            str(previous.get("candidate_status") or previous.get("status") or "")
            in {"Entry Ready", "EXCEPTIONAL"}
            and (_number(previous, "vwap_distance_pct") or 0.0) <= 2.0
        )
    )
    pulse_class = " entry-window-pulse" if just_opened else ""

    if primary is None:
        priority_markup = (
            "<div class='mission-section-title'>WHY #1 TODAY</div>"
            f"<div class='mission-reasons'>{reasons}</div>"
        )
    else:
        priority_markup = (
            f"<div class='mission-why-not'><b>WHY NOT #1</b>"
            f"{html.escape(_secondary_gap(record))}</div>"
        )

    provenance = " · ".join(view["attention_provenance"])
    provenance_markup = (
        f"<div class='small'>Attention source: {html.escape(provenance)}</div>"
        if provenance
        else ""
    )
    context = look_now_context(record, view)
    context_markup = (
        f"<div class='small'><b>Attention type:</b> {html.escape(context)}</div>"
        if context
        else ""
    )

    return (
        f"<div class='mission-target{pulse_class}' style='--mission-color:{view['color']}'>"
        f"<div class='mission-role'>{html.escape(role)}</div>"
        f"<div class='mission-symbol'>{html.escape(item['symbol'])}</div>"
        f"<div class='mission-band'>CONVICTION</div>"
        f"<div class='mission-window-status' style='color:{view['color']}'>"
        f"{html.escape(view['state'])}</div>"
        f"<div class='small'>Confidence cue: {html.escape(cue)}</div>"
        f"<div class='opportunity-meter'>"
        f"<div class='opportunity-meter-top'><span class='opportunity-meter-label'>"
        f"Conviction Meter</span><span class='opportunity-meter-value'>{confidence}% "
        f"<small class='{delta_class}'>{direction} {delta:+d}</small></span></div>"
        f"<div class='opportunity-meter-track' role='progressbar' aria-valuemin='0' "
        f"aria-valuemax='100' aria-valuenow='{confidence}'>"
        f"<div class='opportunity-meter-fill' style='--opportunity:{confidence}%'></div></div></div>"
        f"<div class='small'>{html.escape(view['reason'])}</div>"
        f"{context_markup}"
        f"{priority_markup}"
        f"<div class='mission-section-title'>ENTRY PATH</div>"
        f"<div class='mission-path'>{checklist}</div>"
        f"{provenance_markup}"
        f"<div class='mission-section-title'>GUIDANCE</div>"
        f"<div class='small'>{html.escape(view['next_step'])}</div>"
        f"<div class='mission-meta'>Estimated: <b>{window}</b></div>"
        f"</div>"
    )


def install() -> None:
    """Install a single presentation contract after earlier compatibility layers."""
    from . import ui

    current_mission = ui.walter_mission_control
    if not getattr(current_mission, "_gs310_unified_state", False):
        original_mission = current_mission

        def walter_mission_control(records: list[dict]) -> dict:
            result = deepcopy(original_mission(records))
            for key in ("primary", "secondary"):
                item = result.get(key)
                if isinstance(item, dict) and isinstance(item.get("record"), dict):
                    item["opportunity_state"] = opportunity_state(item["record"])
            return result

        walter_mission_control._gs310_unified_state = True
        walter_mission_control._gs310_original = original_mission
        ui.walter_mission_control = walter_mission_control

    ui._mission_target_markup = _target_markup

    def render_walter_mission_control(records: list[dict]) -> None:
        mission = ui.walter_mission_control(records)
        primary = mission.get("primary")
        secondary = mission.get("secondary")
        if not primary:
            ui.st.markdown(
                "<div class='mission-shell'><div class='mission-title'>🎯 OPPORTUNITY BOARD</div>"
                "No stock deserves elevated attention right now.</div>",
                unsafe_allow_html=True,
            )
            return
        items = [item for item in (primary, secondary) if item]
        states = [opportunity_state(item["record"])["state"] for item in items]
        summary = " · ".join(
            f"{item['symbol']}: {state}" for item, state in zip(items, states)
        )
        monitoring = ""
        if WATCH_FOR_ENTRY not in states:
            monitoring = (
                "<div class='mission-monitoring'>"
                "No entry-ready setups. Continue monitoring.</div>"
            )
        targets = _target_markup(primary, "#1 opportunity")
        if secondary:
            targets += _target_markup(secondary, "#2 opportunity", primary)
        ui.st.markdown(
            f"<div class='mission-shell'><div class='mission-title'>🎯 OPPORTUNITY BOARD</div>"
            f"{monitoring}<div class='small'>{html.escape(summary)}</div>"
            f"<div class='mission-grid'>{targets}</div></div>",
            unsafe_allow_html=True,
        )

    render_walter_mission_control._gs310_unified_state = True
    ui.render_walter_mission_control = render_walter_mission_control

    def render_escalation_engine(records: list[dict]) -> None:
        visible = ui.actionable_candidate_records(records)[:5]
        if not visible:
            ui.st.markdown(
                "<div class='recommendation-box' style='--recommendation-color:#64748b'>"
                "<div class='recommendation-label'>NO CURRENT OPPORTUNITY</div>"
                "<div class='recommendation-message'>"
                "Walter has nothing that warrants elevated review right now.</div></div>",
                unsafe_allow_html=True,
            )
            return
        ui.st.subheader("Walter's Opportunity State")
        ui.st.caption(
            "One interpretation of the same current evidence used on the Opportunity Board."
        )
        for record in visible:
            view = opportunity_state(record)
            evidence = "".join(
                f"<li class='{'delta-up' if entry['passed'] else 'delta-down'}'>"
                f"{'✓' if entry['passed'] else '○'} {html.escape(entry['label'])} · "
                f"{html.escape(entry['detail'])}</li>"
                for entry in view["evidence"]
            )
            context = look_now_context(record, view)
            context_suffix = f" · {context}" if context else ""
            ui.st.markdown(
                f"<div class='recommendation-box' style='--recommendation-color:{view['color']}'>"
                f"<div class='recommendation-label'>"
                f"{html.escape(str(record.get('symbol') or '').upper())} · "
                f"{html.escape(view['state'] + context_suffix)}</div>"
                f"<div class='recommendation-message'>{html.escape(view['reason'])}</div>"
                f"<ul class='escalation-list'>{evidence}</ul>"
                f"<div class='small'>Next: {html.escape(view['next_step'])}</div></div>",
                unsafe_allow_html=True,
            )

    render_escalation_engine._gs310_unified_state = True
    ui.render_escalation_engine = render_escalation_engine
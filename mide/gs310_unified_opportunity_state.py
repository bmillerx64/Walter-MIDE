"""GS310: one display-only opportunity state for Walter's trader-facing surfaces.

The scanner remains the source of truth for discovery, qualification, ranking,
readiness, thresholds, and execution.  This module only translates the current
record into one concise trader-facing state so Mission and Recommendation do not
independently describe the same symbol as EARLY, ENTRY WINDOW, WATCH, and NO TRADE.
"""
from __future__ import annotations

from copy import deepcopy
import html

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
    if any(record.get(key) is True for key in ("halted", "is_halted", "suspended", "is_suspended")):
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
        from .gs309_current_attention_mission import current_attention_provenance

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


def opportunity_state(record: dict) -> dict:
    """Return one current trader-facing state from already-computed evidence."""
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
        {"label": "VWAP", "passed": vwap_near, "detail": "Above / within 2%" if vwap_near else ("Above but extended" if vwap_above else "Not above")},
        {"label": "SuperTrend", "passed": trend, "detail": "Bullish" if trend else "Not confirmed"},
        {"label": "Participation", "passed": participation_pass, "detail": f"{participation:.0f}/100" if participation is not None else "Unavailable"},
        {"label": "Expansion", "passed": expansion_pass, "detail": f"{expansion:.0f}/100" if expansion is not None else "Unavailable"},
    ]

    if _halted(record):
        state = HALTED
        reason = "Trading is halted or suspended."
        next_step = "Watch for resumption, then reassess fresh price, VWAP, trend, and volume."
    elif distance is not None and distance > 2.0:
        state = CHASE_WAIT
        reason = f"Price is {distance:.1f}% above VWAP; the move is extended."
        next_step = "Wait for a reset or constructive pullback toward VWAP before reconsidering."
    elif vwap_near and trend and participation_pass and expansion_pass:
        state = WATCH_FOR_ENTRY
        reason = "VWAP, trend, participation, and expansion are aligned now."
        next_step = "Review the chart for the actual entry; Walter is presenting, not authorizing, the trade."
    elif vwap_above and trend and (participation_pass or expansion_pass or acceleration > 1.0):
        state = DEVELOPING
        missing = [item["label"] for item in evidence if not item["passed"]]
        reason = "Constructive price/trend structure is present, but the setup is still developing."
        next_step = "Need stronger " + " and ".join(missing[:2]).lower() + "." if missing else "Continue monitoring current evidence."
    elif attention:
        state = LOOK_NOW
        reason = "A current attention trigger says this symbol deserves a chart review."
        next_step = "Open the chart and confirm VWAP, SuperTrend, participation, and expansion."
    else:
        state = DEVELOPING
        reason = "Walter is still observing the symbol, but no immediate attention trigger is present."
        next_step = "Keep it in the background until current evidence improves."

    return {
        "state": state,
        "color": STATE_COLORS[state],
        "reason": reason,
        "next_step": next_step,
        "attention_provenance": list(attention),
        "evidence": evidence,
    }


def _target_markup(item: dict, role: str, primary: dict | None = None) -> str:
    record = item["record"]
    view = opportunity_state(record)
    evidence = "".join(
        f"<div class='mission-check'>{'✓' if entry['passed'] else '□'} {html.escape(entry['label'])} · {html.escape(entry['detail'])}</div>"
        for entry in view["evidence"]
    )
    provenance = " · ".join(view["attention_provenance"]) or "Current ranked observation"
    why_not = ""
    if primary is not None:
        why_not = f"<div class='mission-why-not'><b>WHY #2</b>{html.escape(view['reason'])}</div>"
    return (
        f"<div class='mission-target' style='--mission-color:{view['color']}'>"
        f"<div class='mission-role'>{html.escape(role)}</div>"
        f"<div class='mission-symbol'>{html.escape(item['symbol'])}</div>"
        f"<div class='mission-window-status' style='color:{view['color']}'>{html.escape(view['state'])}</div>"
        f"<div class='small'>{html.escape(view['reason'])}</div>"
        f"<div class='mission-section-title'>WHY WALTER IS SHOWING IT</div>"
        f"<div class='mission-reason'>✓ {html.escape(provenance)}</div>"
        f"<div class='mission-section-title'>CURRENT EVIDENCE</div><div class='mission-path'>{evidence}</div>"
        f"<div class='mission-section-title'>NEXT</div><div class='small'>{html.escape(view['next_step'])}</div>"
        f"{why_not}</div>"
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
                "<div class='mission-shell'><div class='mission-title'>🎯 OPPORTUNITY BOARD</div>No stock deserves elevated attention right now.</div>",
                unsafe_allow_html=True,
            )
            return
        items = [item for item in (primary, secondary) if item]
        states = [opportunity_state(item["record"])["state"] for item in items]
        summary = " · ".join(f"{item['symbol']}: {state}" for item, state in zip(items, states))
        targets = _target_markup(primary, "#1 opportunity")
        if secondary:
            targets += _target_markup(secondary, "#2 opportunity", primary)
        ui.st.markdown(
            f"<div class='mission-shell'><div class='mission-title'>🎯 OPPORTUNITY BOARD</div>"
            f"<div class='small'>{html.escape(summary)}</div><div class='mission-grid'>{targets}</div></div>",
            unsafe_allow_html=True,
        )

    render_walter_mission_control._gs310_unified_state = True
    ui.render_walter_mission_control = render_walter_mission_control

    def render_escalation_engine(records: list[dict]) -> None:
        visible = ui.actionable_candidate_records(records)[:5]
        if not visible:
            ui.st.markdown(
                "<div class='recommendation-box' style='--recommendation-color:#64748b'><div class='recommendation-label'>NO CURRENT OPPORTUNITY</div><div class='recommendation-message'>Walter has nothing that warrants elevated review right now.</div></div>",
                unsafe_allow_html=True,
            )
            return
        ui.st.subheader("Walter's Opportunity State")
        ui.st.caption("One interpretation of the same current evidence used on the Opportunity Board.")
        for record in visible:
            view = opportunity_state(record)
            evidence = "".join(
                f"<li class='{'delta-up' if entry['passed'] else 'delta-down'}'>{'✓' if entry['passed'] else '○'} {html.escape(entry['label'])} · {html.escape(entry['detail'])}</li>"
                for entry in view["evidence"]
            )
            ui.st.markdown(
                f"<div class='recommendation-box' style='--recommendation-color:{view['color']}'>"
                f"<div class='recommendation-label'>{html.escape(str(record.get('symbol') or '').upper())} · {html.escape(view['state'])}</div>"
                f"<div class='recommendation-message'>{html.escape(view['reason'])}</div>"
                f"<ul class='escalation-list'>{evidence}</ul>"
                f"<div class='small'>Next: {html.escape(view['next_step'])}</div></div>",
                unsafe_allow_html=True,
            )

    render_escalation_engine._gs310_unified_state = True
    ui.render_escalation_engine = render_escalation_engine

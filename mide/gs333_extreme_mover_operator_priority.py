"""GS333: prioritize extreme current movers and keep diagnostics off the Radar sightline.

This is presentation-only. It does not change discovery membership, gates, scores,
thresholds, ranking, readiness, execution, or news semantics.

Two operator problems are addressed:
* A live top mover can be a major market event without being a good entry. Walter
  should put that event in front of the trader while preserving DO NOT CHASE / halt
  resume discipline.
* System Status, Decision Funnel audit trails, and voice transport diagnostics are
  maintenance information. In a live Streamlit run they belong in the sidebar,
  not between the current recommendation and the rest of the Radar results.
"""
from __future__ import annotations

import html
from typing import Iterable

EXTREME_MOVER_PCT = 75.0


def _number(record: dict, *keys: str, default: float | None = None) -> float | None:
    for key in keys:
        value = record.get(key)
        if value is None:
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return default


def _headline(record: dict) -> str:
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


def _attention(record: dict) -> tuple[str, ...]:
    try:
        from .gs309_current_attention_mission import current_attention_provenance

        return tuple(current_attention_provenance(record))
    except Exception:
        return ()


def _halted(record: dict) -> bool:
    if any(record.get(key) is True for key in ("halted", "is_halted", "suspended", "is_suspended")):
        return True
    text = " ".join(
        str(record.get(key) or "")
        for key in ("halt_status", "trading_status", "market_status", "status_reason")
    ).lower()
    return "halt" in text or "suspend" in text


def extreme_market_event(record: dict) -> dict | None:
    """Describe an extraordinary *attention* event without granting entry status."""
    pct_change = _number(record, "pct_change", default=0.0) or 0.0
    provenance = _attention(record)
    current = bool({"WEBULL_TOP_MOVER", "FRESH_NEWS_SEED"}.intersection(provenance))
    if pct_change < EXTREME_MOVER_PCT or not current:
        return None

    distance = _number(record, "vwap_distance_pct")
    relation = str(record.get("vwap_relation") or "").lower()
    trend = bool(record.get("supertrend_bullish") or record.get("supertrend_flip"))
    halted = _halted(record)
    headline = _headline(record)

    if halted:
        label = "HALTED · WATCH RESUME"
        guidance = "Do not anticipate the reopen. Reassess fresh price, VWAP, trend, and volume after trading resumes."
    elif distance is not None and distance > 5.0:
        label = "EXTREME MOVER · DO NOT CHASE"
        guidance = "Major market event, not an entry signal. Wait for a constructive reset or halt/resume setup before reconsidering."
    else:
        label = "EXTREME MOVER · LOOK NOW"
        guidance = "Open the chart now, but require the normal entry evidence before considering a trade."

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


def prioritized_extreme_event(records: Iterable[dict]) -> tuple[dict | None, dict | None]:
    choices: list[tuple[tuple, dict, dict]] = []
    for record in records or []:
        event = extreme_market_event(record)
        if not event:
            continue
        dollar_volume = _number(record, "dollar_volume", default=0.0) or 0.0
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
    trend = "SuperTrend bullish" if event.get("trend") else "SuperTrend not confirmed"
    headline = str(event.get("headline") or "").strip()
    catalyst = (
        f"<div class='small' style='margin-top:8px'><b>Catalyst:</b> {html.escape(headline)}</div>"
        if headline
        else ""
    )
    return (
        "<div class='recommendation-box' style='--recommendation-color:#facc15'>"
        f"<div class='recommendation-label'>{html.escape(event['symbol'])} · {html.escape(event['label'])}</div>"
        f"<div class='recommendation-message'>Current move: +{float(event['pct_change']):.1f}% · "
        f"{html.escape(vwap)} · {html.escape(trend)}</div>"
        f"{catalyst}"
        f"<div class='small' style='margin-top:8px'><b>Walter:</b> {html.escape(event['guidance'])}</div>"
        "</div>"
    )


def _in_streamlit_run() -> bool:
    try:
        from streamlit.runtime.scriptrunner import get_script_run_ctx

        return get_script_run_ctx(suppress_warning=True) is not None
    except Exception:
        return False


def _inherit_wrapper_contract(wrapper, wrapped) -> None:
    """Preserve prior GS introspection contracts when layering presentation wrappers."""
    for name, value in getattr(wrapped, "__dict__", {}).items():
        if name.startswith("_gs") and not hasattr(wrapper, name):
            setattr(wrapper, name, value)


def install() -> None:
    from . import ui

    if getattr(ui.render_walter_mission_control, "_gs333_operator_priority", False):
        return

    # GS332's live action renderer closes over the established concise GS310
    # recommendation. Keep that contract and only add an extraordinary-event cue
    # ahead of ordinary recommendations.
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

    _inherit_wrapper_contract(render_action_first, current_action)
    render_action_first._gs333_operator_priority = True
    render_action_first._gs333_original = current_action
    ui.render_walter_mission_control = render_action_first

    # In live Streamlit only, route the two maintenance expanders to the sidebar.
    # Unit tests and non-Streamlit callers retain the original Streamlit contract.
    import streamlit as st

    current_expander = st.expander
    if not getattr(current_expander, "_gs333_diagnostics_sidebar", False):
        diagnostic_labels = {"System Status", "Decision Funnel audit trails"}

        def diagnostic_expander(label, *args, **kwargs):
            if _in_streamlit_run() and str(label) in diagnostic_labels:
                return st.sidebar.expander(str(label), *args, **kwargs)
            return current_expander(label, *args, **kwargs)

        _inherit_wrapper_contract(diagnostic_expander, current_expander)
        diagnostic_expander._gs333_diagnostics_sidebar = True
        diagnostic_expander._gs333_original = current_expander
        st.expander = diagnostic_expander
        ui.st.expander = diagnostic_expander

    # Keep speech transport intact, but render its observability strip with the
    # other maintenance controls in the sidebar instead of interrupting Radar.
    current_play_alert = ui.play_alert
    if not getattr(current_play_alert, "_gs333_voice_sidebar", False):
        def play_alert_in_sidebar(*args, **kwargs):
            if _in_streamlit_run():
                with st.sidebar.expander("Voice transport", expanded=False):
                    return current_play_alert(*args, **kwargs)
            return current_play_alert(*args, **kwargs)

        _inherit_wrapper_contract(play_alert_in_sidebar, current_play_alert)
        play_alert_in_sidebar._gs333_voice_sidebar = True
        play_alert_in_sidebar._gs333_original = current_play_alert
        ui.play_alert = play_alert_in_sidebar

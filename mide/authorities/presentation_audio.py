"""Authoritative Walter Next Presentation + Audio boundary.

Presentation consumes authoritative evidence/state and renders or announces it. Legacy
UI functions are resolved dynamically so importing this authority during startup can
never freeze an older wrapper implementation.
"""

from __future__ import annotations

from functools import wraps


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

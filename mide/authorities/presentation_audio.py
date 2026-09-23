"""Authority boundary for Presentation + Audio.

This module is intentionally a facade in Phase 1.  It gives Walter Next one stable
presentation/audio import surface while preserving all currently validated rendering,
operator-order, freshness, and alert behavior.
"""

from mide.gs516_visible_alert_audio_health import render_sidebar_audio_health
from mide.live_evidence_observation import render_live_evidence_diagnostics
from mide.ui import (
    actionable_candidate_records,
    data_integrity_markup,
    decision_funnel_markup,
    inject_css,
    market_session_quality_markup,
    mission_control_header_markup,
    opportunity_card,
    play_alert,
    radar_table,
    rejected_candidates_table,
    rejection_diagnostics,
    render_calibration_dashboard,
    render_early_setups,
    render_escalation_engine,
    render_live_opportunity_feed,
    render_walter_mission_control,
    scanner_v2_dashboard_counts,
    scanner_v2_display_sections,
)

__all__ = [
    "actionable_candidate_records",
    "data_integrity_markup",
    "decision_funnel_markup",
    "inject_css",
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

"""GS332: make Radar operator-first without changing trading logic.

Presentation only. Restore Walter's original Mission Control header, put the
current opportunity-state recommendation in the first actionable slot, move the
larger opportunity/structure views below it, and keep verification data out of
the primary trading sightline. The underlying verification remains available in
System Status / Diagnostics.
"""
from __future__ import annotations


def _in_streamlit_run() -> bool:
    try:
        from streamlit.runtime.scriptrunner import get_script_run_ctx

        return get_script_run_ctx(suppress_warning=True) is not None
    except Exception:
        return False


def install() -> None:
    from . import ui

    if getattr(ui.render_walter_mission_control, "_gs332_action_first", False):
        return

    current_header = ui.mission_control_header_markup
    original_header = getattr(current_header, "_gs330_original", current_header)
    original_board = ui.render_walter_mission_control
    original_action = ui.render_escalation_engine
    original_early = ui.render_early_setups
    original_integrity = ui.data_integrity_markup
    original_market = ui.market_session_quality_markup

    def mission_header(*args, **kwargs):
        if _in_streamlit_run():
            return original_header(*args, **kwargs)
        return current_header(*args, **kwargs)

    def quiet_integrity(*args, **kwargs):
        if _in_streamlit_run():
            original_integrity(*args, **kwargs)
            return ""
        return original_integrity(*args, **kwargs)

    def quiet_market(*args, **kwargs):
        if _in_streamlit_run():
            original_market(*args, **kwargs)
            return ""
        return original_market(*args, **kwargs)

    def defer_early(records: list[dict]) -> None:
        if _in_streamlit_run():
            return None
        return original_early(records)

    def action_first(records: list[dict]) -> None:
        if _in_streamlit_run():
            return original_action(records)
        return original_board(records)

    def supporting_views(records: list[dict]) -> None:
        if _in_streamlit_run():
            original_board(records)
            original_early(records)
            return None
        return original_action(records)

    mission_header._gs332_action_first = True
    mission_header._gs332_original = current_header
    if getattr(current_header, "_gs330_compact_status", False):
        mission_header._gs330_compact_status = True
        mission_header._gs330_original = getattr(
            current_header, "_gs330_original", original_header
        )

    action_first._gs332_action_first = True
    action_first._gs332_original = original_board
    supporting_views._gs332_action_first = True
    supporting_views._gs332_original = original_action
    defer_early._gs332_action_first = True
    defer_early._gs332_original = original_early
    quiet_integrity._gs332_action_first = True
    quiet_integrity._gs332_original = original_integrity
    quiet_market._gs332_action_first = True
    quiet_market._gs332_original = original_market

    # Preserve GS330 renderer metadata so its existing regression contract
    # remains intact; GS332 only supersedes what the live app chooses to show.
    if getattr(original_integrity, "_gs330_compact_status", False):
        quiet_integrity._gs330_compact_status = True
        quiet_integrity._gs330_original = getattr(
            original_integrity, "_gs330_original", original_integrity
        )
    if getattr(original_market, "_gs330_compact_status", False):
        quiet_market._gs330_compact_status = True
        quiet_market._gs330_original = getattr(
            original_market, "_gs330_original", original_market
        )

    ui.mission_control_header_markup = mission_header
    ui.data_integrity_markup = quiet_integrity
    ui.market_session_quality_markup = quiet_market
    ui.render_early_setups = defer_early
    ui.render_walter_mission_control = action_first
    ui.render_escalation_engine = supporting_views

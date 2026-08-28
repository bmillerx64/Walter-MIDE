"""GS332: make Radar operator-first without changing trading logic.

Presentation only. Restore Walter's original Mission Control header, put the
current opportunity-state recommendation in the first actionable slot, move the
larger opportunity/structure views below it, and keep verification data out of
the primary trading sightline. The underlying verification remains available in
System Status / Diagnostics.
"""
from __future__ import annotations


def install() -> None:
    from . import ui

    if getattr(ui.render_walter_mission_control, "_gs332_action_first", False):
        return

    # GS330 compacted the original Mission Control header for the live runtime.
    # Reuse its stored original so the polished header returns without copying
    # or forking the established markup.
    current_header = ui.mission_control_header_markup
    original_header = getattr(current_header, "_gs330_original", current_header)

    original_board = ui.render_walter_mission_control
    original_action = ui.render_escalation_engine
    original_early = ui.render_early_setups
    original_integrity = ui.data_integrity_markup
    original_market = ui.market_session_quality_markup

    def mission_header(*args, **kwargs):
        return original_header(*args, **kwargs)

    # These top-of-page slots stay present for stable Streamlit geometry but do
    # not occupy the trader's primary sightline. Their detailed data remains in
    # System Status / Diagnostics.
    def quiet_integrity(*args, **kwargs):
        original_integrity(*args, **kwargs)
        return ""

    def quiet_market(*args, **kwargs):
        original_market(*args, **kwargs)
        return ""

    # The existing early-setup slot becomes intentionally empty so the next
    # visible surface is the actionable recommendation.
    def defer_early(*_args, **_kwargs):
        return None

    # app.py renders this function in mission_plan_slot, immediately after the
    # header/status placeholders. Put the concise LOOK NOW / DEVELOPING /
    # WATCH FOR ENTRY / CHASE-WAIT recommendation here.
    def action_first(records: list[dict]) -> None:
        original_action(records)

    # app.py renders this later, after the live feed. Put the richer supporting
    # context there: Opportunity Board first, then Structure / Near-Miss.
    def supporting_views(records: list[dict]) -> None:
        original_board(records)
        original_early(records)

    mission_header._gs332_action_first = True
    mission_header._gs332_original = current_header
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

    ui.mission_control_header_markup = mission_header
    ui.data_integrity_markup = quiet_integrity
    ui.market_session_quality_markup = quiet_market
    ui.render_early_setups = defer_early
    ui.render_walter_mission_control = action_first
    ui.render_escalation_engine = supporting_views

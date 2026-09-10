"""GS414: anchor Opportunity State ordering after the final enrichment pass.

Live validation on 2026-09-10 exposed the same presentation failure GS401 was meant
to prevent: an already-extended CHASE / WAIT symbol rendered above later-enriched
DEVELOPING symbols. The underlying candidate/state evidence was correct; only the
visible sequence was wrong.

GS414 makes the final Opportunity State renderer consume one frozen, canonically
ordered enriched collection for the duration of that render. This prevents nested
renderer/actionable wrappers from appending or reordering awareness records after the
priority sort.

Presentation only. It does not change discovery, candidate membership, Webull market
data, VWAP/SuperTrend evidence, participation, expansion, scoring, ranking,
qualification, thresholds, readiness, alerts/audio, execution, or orders.
"""
from __future__ import annotations


def _inherit(wrapper, wrapped) -> None:
    for name, value in getattr(wrapped, "__dict__", {}).items():
        if name.startswith("_gs") and not hasattr(wrapper, name):
            setattr(wrapper, name, value)


def _install_gs419() -> None:
    from .gs419_completed_scan_heartbeat import install as install_gs419

    install_gs419()


def final_enriched_opportunity_records(
    records: list[dict], *, actionable_function=None
) -> list[dict]:
    """Build the complete enriched presentation collection, then sort it once."""
    from . import ui
    from .gs369_escalation_priority_order import ordered_escalation_records

    actionable = actionable_function or ui.actionable_candidate_records
    enriched = list(actionable(records) or [])
    return ordered_escalation_records(enriched)


def install() -> None:
    """Freeze final enrichment/order across the complete Opportunity State render."""
    from . import ui

    current = ui.render_escalation_engine
    if getattr(current, "_gs414_final_enriched_opportunity_order", False):
        # Warm Streamlit processes may already own GS414 when newer late installers
        # arrive; still converge the audio-only GS419 tail without a process restart.
        _install_gs419()
        return

    def render_with_final_enriched_order(records: list[dict]) -> None:
        public_actionable = ui.actionable_candidate_records
        ordered = final_enriched_opportunity_records(
            records,
            actionable_function=public_actionable,
        )

        # Every nested Opportunity State wrapper must see the same already-enriched,
        # already-ordered snapshot. The public callable is restored immediately after
        # rendering so no scanner, alert, mission, or later dashboard path is changed.
        def frozen_actionable(_records: list[dict]) -> list[dict]:
            return list(ordered)

        _inherit(frozen_actionable, public_actionable)
        ui.actionable_candidate_records = frozen_actionable
        try:
            return current(list(ordered))
        finally:
            ui.actionable_candidate_records = public_actionable

    _inherit(render_with_final_enriched_order, current)
    render_with_final_enriched_order._gs414_final_enriched_opportunity_order = True
    render_with_final_enriched_order._gs414_original = current
    ui.render_escalation_engine = render_with_final_enriched_order
    _install_gs419()

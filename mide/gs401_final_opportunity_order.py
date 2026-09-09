"""GS401: lock operator-state priority at the final Opportunity State render boundary.

Live 2026-09-09 validation showed CHASE / WAIT cards above DEVELOPING cards again after
a warm deployment. GS392 correctly sorts the records before the renderer, but the
canonical GS310 renderer subsequently calls ``actionable_candidate_records`` inside
itself. Later visibility/awareness/reclaim layers are allowed to enrich that
presentation collection, so the outer sort can be undone before the cards are drawn.

GS401 removes that wrapper-order dependency without replacing the established render
stack. During the final Opportunity State render only, it makes the renderer's internal
``actionable_candidate_records`` call return the existing enriched collection in the
canonical GS369 state order, then restores the original callable immediately afterward.
The existing renderer still owns all markup and all inherited wrapper contracts.

Presentation only. No discovery, market data, VWAP/ST evidence, scoring, qualification,
readiness, thresholds, alert truth, execution, or orders are changed.
"""
from __future__ import annotations


def _inherit(wrapper, wrapped) -> None:
    for name, value in getattr(wrapped, "__dict__", {}).items():
        if name.startswith("_gs") and not hasattr(wrapper, name):
            setattr(wrapper, name, value)


def final_visible_records(records: list[dict]) -> list[dict]:
    """Return the final five operator cards after all visibility enrichment is done."""
    from . import ui
    from .gs369_escalation_priority_order import ordered_escalation_records

    actionable = ui.actionable_candidate_records(records)
    return ordered_escalation_records(actionable)[:5]


def install() -> None:
    """Pin post-filter ordering while preserving the complete existing renderer stack."""
    from . import ui
    from .gs369_escalation_priority_order import ordered_escalation_records

    current = ui.render_escalation_engine
    if getattr(current, "_gs401_final_opportunity_order", False):
        return

    def render_with_final_opportunity_order(records: list[dict]) -> None:
        original_actionable = ui.actionable_candidate_records

        def final_actionable_records(rows: list[dict]) -> list[dict]:
            enriched = original_actionable(rows)
            return ordered_escalation_records(enriched)

        # GS310 performs its five-card slice after calling actionable_candidate_records.
        # Make that one internal call observe the canonical order, but keep every
        # existing renderer/wrapper intact and restore the public callable immediately.
        ui.actionable_candidate_records = final_actionable_records
        try:
            return current(ordered_escalation_records(records))
        finally:
            ui.actionable_candidate_records = original_actionable

    _inherit(render_with_final_opportunity_order, current)
    render_with_final_opportunity_order._gs401_final_opportunity_order = True
    render_with_final_opportunity_order._gs401_original = current
    ui.render_escalation_engine = render_with_final_opportunity_order

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

GS538 closes a later wrapper-chain regression exposed live on 2026-09-23: GS401 had
captured the ordering callable when it installed, before GS497/GS517 later became the
final operator-priority authority. The nested renderer could therefore re-sort a
correctly ordered outer snapshot with stale rules and place CHASE / WAIT above a
green WATCH FOR ENTRY card. GS401 now resolves the canonical GS369 sorter dynamically
at render time, so the final live card stack consumes the current ordering contract.
The existing renderer still owns all markup and all inherited wrapper contracts.

Presentation only. No discovery, market data, VWAP/ST evidence, scoring, qualification,
readiness, thresholds, alert truth, execution, or orders are changed.
"""
from __future__ import annotations


def _inherit(wrapper, wrapped) -> None:
    for name, value in getattr(wrapped, "__dict__", {}).items():
        if name.startswith("_gs") and not hasattr(wrapper, name):
            setattr(wrapper, name, value)


def _presentation_audio():
    from mide.authorities import presentation_audio

    return presentation_audio


def final_visible_records(records: list[dict]) -> list[dict]:
    """Warm-deploy-safe facade for authoritative final Opportunity ordering."""
    current = getattr(
        _presentation_audio(),
        "final_visible_opportunity_records",
        None,
    )
    if callable(current):
        return current(records)

    # Retained-runtime fallback for an older Presentation + Audio generation.
    from . import gs369_escalation_priority_order as gs369
    from . import ui

    actionable = ui.actionable_candidate_records(records)
    return gs369.ordered_escalation_records(actionable)[:5]


def install() -> None:
    """Warm-deploy-safe facade for GS401's final render-order binding."""
    authority = getattr(
        _presentation_audio(),
        "install_final_opportunity_order",
        None,
    )
    if callable(authority):
        authority()
        return

    # Retained-runtime fallback for an older Presentation + Audio generation.
    from . import gs369_escalation_priority_order as gs369
    from . import ui

    current = ui.render_escalation_engine
    if getattr(current, "_gs401_final_opportunity_order", False):
        return

    def render_with_final_opportunity_order(records: list[dict]) -> None:
        original_actionable = ui.actionable_candidate_records

        def final_actionable_records(rows: list[dict]) -> list[dict]:
            enriched = original_actionable(rows)
            # GS538: resolve the final sorter now, not when this wrapper installed.
            return gs369.ordered_escalation_records(enriched)

        ui.actionable_candidate_records = final_actionable_records
        try:
            return current(gs369.ordered_escalation_records(records))
        finally:
            ui.actionable_candidate_records = original_actionable

    _inherit(render_with_final_opportunity_order, current)
    render_with_final_opportunity_order._gs401_final_opportunity_order = True
    render_with_final_opportunity_order._gs401_original = current
    ui.render_escalation_engine = render_with_final_opportunity_order

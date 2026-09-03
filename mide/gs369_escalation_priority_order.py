"""GS369: apply Walter's existing attention hierarchy to Opportunity State cards.

Presentation-only.  GS363 already defines Walter's operator ordering contract:
WATCH FOR ENTRY, LOOK NOW, DEVELOPING, CHASE / WAIT, then HALTED, with the existing
0-100 attention score used inside each state.  Live validation on 2026-09-03 showed
that the compact priority queue and Developing detail honored that contract while
Walter's top "Opportunity State" card stack still rendered the unsorted incoming
candidate order.  That could place CHASE / WAIT above a genuine LOOK NOW.

This layer only sorts the records passed to the existing escalation renderer.  It
does not change discovery, candidate membership, market data, scoring, ranking,
qualification, thresholds, readiness, alerts, execution, or orders.
"""
from __future__ import annotations


def ordered_escalation_records(records: list[dict]) -> list[dict]:
    """Return a presentation-only copy in Walter's established attention order."""
    from .gs363_operator_attention_hierarchy import sorted_operator_records

    return sorted_operator_records(list(records or []))


def _inherit(wrapper, wrapped) -> None:
    for name, value in getattr(wrapped, "__dict__", {}).items():
        if name.startswith("_gs") and not hasattr(wrapper, name):
            setattr(wrapper, name, value)


def install() -> None:
    """Make Walter's Opportunity State card stack honor GS363 ordering."""
    from . import ui

    current = ui.render_escalation_engine
    if getattr(current, "_gs369_escalation_priority_order", False):
        return

    def render_escalation_engine(records: list[dict]) -> None:
        return current(ordered_escalation_records(records))

    _inherit(render_escalation_engine, current)
    render_escalation_engine._gs369_escalation_priority_order = True
    render_escalation_engine._gs369_original = current
    ui.render_escalation_engine = render_escalation_engine

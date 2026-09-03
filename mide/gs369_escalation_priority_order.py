"""GS369/GS370: enforce Walter's attention hierarchy on the live card routes.

Presentation-only. GS363 defines Walter's operator ordering contract:
WATCH FOR ENTRY, LOOK NOW, DEVELOPING, CHASE / WAIT, then HALTED, with the existing
0-100 attention score used inside each state.

GS369 sorted ``ui.render_escalation_engine``. Live validation after that merge
showed the visible top ``Walter's Opportunity State`` stack could still render
CHASE / WAIT above DEVELOPING. The reason is GS332's action-first routing: in a
live Streamlit run, the top opportunity-state cards are reached through
``ui.render_walter_mission_control`` while the function named
``render_escalation_engine`` is repurposed for supporting views.

GS370 therefore applies the same presentation-only ordering to both public render
routes. Each route installs independently so an already-installed GS369 wrapper
cannot cause the live mission-control route to be skipped on a warm deployment.

No discovery, candidate membership, market data, scoring, ranking, qualification,
thresholds, readiness, alerts, execution, or orders are changed.
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


def _install_ordered_renderer(ui, attr: str, marker: str) -> None:
    """Wrap one UI renderer without letting another route's marker short-circuit it."""
    current = getattr(ui, attr)
    if getattr(current, marker, False):
        return

    def ordered_renderer(records: list[dict]) -> None:
        return current(ordered_escalation_records(records))

    _inherit(ordered_renderer, current)
    setattr(ordered_renderer, marker, True)
    ordered_renderer._gs370_original = current
    setattr(ui, attr, ordered_renderer)


def install() -> None:
    """Make both live Opportunity State routes honor the GS363 hierarchy."""
    from . import ui

    # GS369's nominal escalation route remains sorted for supporting/non-live
    # callers and compatibility tests.
    _install_ordered_renderer(
        ui,
        "render_escalation_engine",
        "_gs369_escalation_priority_order",
    )

    # GS332 action-first routing sends the live top Opportunity State stack through
    # render_walter_mission_control. This is the route live validation proved was
    # still unsorted after GS369.
    _install_ordered_renderer(
        ui,
        "render_walter_mission_control",
        "_gs370_live_opportunity_state_priority_order",
    )

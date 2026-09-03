"""GS369/GS370/GS371: enforce Walter's attention hierarchy on live cards.

Presentation-only. GS363 defines Walter's operator ordering contract:
WATCH FOR ENTRY, LOOK NOW, DEVELOPING, CHASE / WAIT, then HALTED, with the existing
0-100 attention score used inside each state.

GS369 sorted the nominal escalation renderer and GS370 added the GS332 live
mission-control route. Live validation of the merged GS370 build still showed a
DEVELOPING card below CHASE / WAIT cards. Two warm-runtime hazards remained:
renderer wrappers can be bypassed by app-level references, and GS363's imported
``opportunity_state`` binding can lag the current calibrated GS310 state function.

GS371 keeps the wrappers for compatibility but makes this sorter resolve the
current canonical GS310 opportunity state at call time. app.py also applies this
sort directly to the two operator rendering calls, so visible ordering no longer
depends on wrapper/import timing.

No discovery, candidate membership, market data, scoring, ranking, qualification,
thresholds, readiness, alerts, execution, or orders are changed.
"""
from __future__ import annotations


def ordered_escalation_records(records: list[dict]) -> list[dict]:
    """Return a presentation-only copy in the current canonical state order.

    Resolve ``unified.opportunity_state`` dynamically instead of delegating the
    state key to GS363's module-level imported binding. This keeps sorting on the
    same calibrated state function that renders the Opportunity State cards even
    when Streamlit retains older module objects across a warm deployment.
    """
    from . import gs310_unified_opportunity_state as unified
    from . import ui
    from .gs363_operator_attention_hierarchy import (
        STATE_PRIORITY,
        operator_attention_score,
    )

    rows = list(records or [])
    rows.sort(key=lambda record: str(record.get("symbol") or "").upper())
    try:
        rows.sort(key=ui.trader_priority_sort_key, reverse=True)
    except Exception:
        pass
    rows.sort(key=operator_attention_score, reverse=True)
    rows.sort(
        key=lambda record: STATE_PRIORITY.get(
            unified.opportunity_state(record)["state"], 0
        ),
        reverse=True,
    )
    return rows


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
    """Make both live Opportunity State routes honor the operator hierarchy."""
    from . import ui

    _install_ordered_renderer(
        ui,
        "render_escalation_engine",
        "_gs369_escalation_priority_order",
    )
    _install_ordered_renderer(
        ui,
        "render_walter_mission_control",
        "_gs370_live_opportunity_state_priority_order",
    )

"""GS401: lock operator-state priority at the final Opportunity State render boundary.

Live 2026-09-09 validation showed CHASE / WAIT cards above DEVELOPING cards again after
a warm deployment. GS392 correctly sorts the records before the renderer, but the
canonical GS310 renderer subsequently calls ``actionable_candidate_records`` inside
itself. Later visibility/awareness/reclaim layers are allowed to enrich that
presentation collection, so the outer sort can be undone before the cards are drawn.

GS401 removes that wrapper-order dependency for this surface. It performs the existing
actionable/visibility filtering first, then applies the existing GS369 state-priority
sort immediately before the five Opportunity State cards are rendered.

Presentation only. No discovery, market data, VWAP/ST evidence, scoring, qualification,
readiness, thresholds, alert truth, execution, or orders are changed.
"""
from __future__ import annotations

import html


def final_visible_records(records: list[dict]) -> list[dict]:
    """Return the final five operator cards after all visibility enrichment is done."""
    from . import ui
    from .gs369_escalation_priority_order import ordered_escalation_records

    actionable = ui.actionable_candidate_records(records)
    return ordered_escalation_records(actionable)[:5]


def render_final_opportunity_state(records: list[dict]) -> None:
    """Render GS310 Opportunity State cards in the final canonical attention order."""
    from . import ui
    from .gs310_unified_opportunity_state import opportunity_state

    visible = final_visible_records(records)
    if not visible:
        ui.st.markdown(
            "<div class='recommendation-box' style='--recommendation-color:#64748b'>"
            "<div class='recommendation-label'>NO CURRENT OPPORTUNITY</div>"
            "<div class='recommendation-message'>"
            "Walter has nothing that warrants elevated review right now.</div></div>",
            unsafe_allow_html=True,
        )
        return

    ui.st.subheader("Walter's Opportunity State")
    ui.st.caption(
        "One interpretation of the same current evidence used on the Opportunity Board."
    )
    for record in visible:
        view = opportunity_state(record)
        evidence = "".join(
            f"<li class='{'delta-up' if entry['passed'] else 'delta-down'}'>"
            f"{'✓' if entry['passed'] else '○'} {html.escape(entry['label'])} · "
            f"{html.escape(entry['detail'])}</li>"
            for entry in view["evidence"]
        )
        ui.st.markdown(
            f"<div class='recommendation-box' style='--recommendation-color:{view['color']}'>"
            f"<div class='recommendation-label'>"
            f"{html.escape(str(record.get('symbol') or '').upper())} · "
            f"{html.escape(view['state'])}</div>"
            f"<div class='recommendation-message'>{html.escape(view['reason'])}</div>"
            f"<ul class='escalation-list'>{evidence}</ul>"
            f"<div class='small'>Next: {html.escape(view['next_step'])}</div></div>",
            unsafe_allow_html=True,
        )


def install() -> None:
    """Replace only the final Opportunity State renderer; remain idempotent."""
    from . import ui

    current = ui.render_escalation_engine
    if getattr(current, "_gs401_final_opportunity_order", False):
        return

    render_final_opportunity_state._gs401_final_opportunity_order = True
    render_final_opportunity_state._gs401_original = current
    ui.render_escalation_engine = render_final_opportunity_state

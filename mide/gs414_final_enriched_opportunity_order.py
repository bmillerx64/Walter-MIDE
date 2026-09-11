"""GS414/GS436: anchor Opportunity State ordering after final enrichment.

Live validation on 2026-09-10 exposed the same presentation failure GS401 was meant
to prevent: an already-extended CHASE / WAIT symbol rendered above later-enriched
DEVELOPING symbols. The underlying candidate/state evidence was correct; only the
visible sequence was wrong.

GS414 makes the final Opportunity State renderer consume one frozen, canonically
ordered enriched collection for the duration of that render. This prevents nested
renderer/actionable wrappers from appending or reordering awareness records after the
priority sort.

GS436 closes the remaining warm-runtime failure seen on 2026-09-11. Walter's wrapper
helpers intentionally inherit ``_gs*`` markers for compatibility. A later/stale
renderer can therefore carry GS414's marker even when the actual GS414 wrapper is no
longer the outer render boundary. Treating that inherited marker as installation
proof lets CHASE / WAIT render above LOOK NOW or DEVELOPING again. GS436 uses a
private non-inherited owner sentinel instead and re-runs this installer at the final
late-runtime boundary, so only the actual outer GS414 wrapper can suppress rebinding.

Presentation only. It does not change discovery, candidate membership, Webull market
data, VWAP/SuperTrend evidence, participation, expansion, scoring, ranking,
qualification, thresholds, readiness, alerts/audio, execution, or orders.
"""
from __future__ import annotations


# Deliberately does not begin with ``_gs``. Walter's compatibility wrappers inherit
# ``_gs*`` markers; this owner sentinel must identify the actual outer callable only.
FINAL_ORDER_OWNER_ATTR = "_walter_final_enriched_opportunity_order_owner"


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
    if getattr(current, FINAL_ORDER_OWNER_ATTR, False):
        # This is proof that the actual outer renderer is GS414/GS436. An inherited
        # ``_gs414...`` marker alone is intentionally not sufficient.
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
    render_with_final_enriched_order._gs436_final_render_hard_bind = True
    render_with_final_enriched_order._gs414_original = current
    setattr(render_with_final_enriched_order, FINAL_ORDER_OWNER_ATTR, True)
    ui.render_escalation_engine = render_with_final_enriched_order
    _install_gs419()

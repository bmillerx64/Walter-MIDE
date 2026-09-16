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

GS462 uses this final late-runtime boundary to reassert its presentation-only 30s/1m
pre-flip attention layer after GS459/GS460/GS461 have converged. GS463 then applies
its attention/state ordering layer. GS464 restores session-aware VWAP authority after
the older GS391 installer has completed. GS465 makes the visible card stack strictly
state-contiguous and cleans up extreme-mover language. GS466 then reasserts the
operator-awareness freshness exception for current extreme leaders whose source bars
freeze during a halt/pause, without restoring any trade authority.

GS414/GS436/GS462/GS463/GS465/GS466 remain presentation-only. GS464 owns its separate
VWAP-truth contract and changes no thresholds, qualification, readiness, execution,
or orders.
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


def _install_gs462() -> None:
    """Reassert the final presentation-only pre-flip attention wrapper."""
    from .gs462_preflip_ignition_watch import install as install_gs462

    install_gs462()


def _install_gs463() -> None:
    """Reassert the state/attention ordering wrapper before GS465 cleanup."""
    from .gs463_state_first_operator_order import install as install_gs463

    install_gs463()


def _install_gs464() -> None:
    """Restore session-aware primary VWAP after the legacy GS391 chain converges."""
    from .gs464_session_aware_vwap_parity import install as install_gs464

    install_gs464()


def _install_gs465() -> None:
    """Make final visible card order state-contiguous and extreme labels truthful."""
    from .gs465_presentation_priority_cleanup import install as install_gs465

    install_gs465()


def _install_gs466() -> None:
    """Keep frozen current extreme leaders visible in awareness-only presentation."""
    from .gs466_extreme_awareness_continuity import install as install_gs466

    install_gs466()


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

    # GS391 lives inside the legacy late chain. Reassert GS464 first so all subsequent
    # evidence/presentation layers see the same session-aware primary VWAP authority.
    # GS465 remains the final card-order contract; GS466 changes only visibility of
    # awareness-only current extremes before that ordered collection is frozen.
    _install_gs464()
    _install_gs462()
    _install_gs463()
    _install_gs465()
    _install_gs466()

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

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
state-contiguous and cleans up extreme-mover language. GS466 reasserts the
operator-awareness freshness exception for current extreme leaders whose source bars
freeze during a halt/pause. GS467 narrows standalone legacy 1m ignition so it cannot
manufacture LOOK NOW without stronger bottom-up structure. GS468 is the final VWAP
truth veto: numeric current price/VWAP evidence that says below cannot render as LOOK
NOW or WATCH FOR ENTRY even when an older categorical field says otherwise. GS474
then expires GS460 compression-owned LOOK NOW once the newly joined timeframe rung
is no longer fresh, so an urgent verb cannot persist as a stale condition. GS475
hard-binds session-aware Webull snapshot price truth at the same late-runtime boundary
so PRE/ATH movers cannot enter the existing pipeline with a stale RTH price. GS477
adds bounded presentation/audio memory for a proven leader that resets toward VWAP
and re-ignites. Its record enrichment occurs only on GS414's detached render snapshot,
so the exact public actionable callable is still restored even when rendering fails.

GS414/GS436/GS462/GS463/GS465/GS466/GS467/GS468/GS474/GS477 remain presentation-only.
GS464 owns its separate VWAP-truth calculation contract. GS475 owns only snapshot
source-price truth. None changes qualification, readiness, execution, or orders.
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


def _install_gs467() -> None:
    """Narrow standalone legacy 1m ignition LOOK NOW semantics."""
    from .gs467_look_now_semantic_consolidation import install as install_gs467

    install_gs467()


def _install_gs468() -> None:
    """Make numeric current VWAP truth a final urgency veto."""
    from .gs468_vwap_truth_veto import install as install_gs468

    install_gs468()


def _install_gs474() -> None:
    """Expire only stale GS460 compression-owned LOOK NOW urgency."""
    from .gs474_fresh_look_now_expiry import install as install_gs474

    install_gs474()


def _install_gs475() -> None:
    """Hard-bind session-aware Webull snapshot source-price truth."""
    from .gs475_premarket_snapshot_truth import install as install_gs475

    install_gs475()


def _install_gs477() -> None:
    """Bind leader-reset state/audio without owning the public actionable callable."""
    from .gs477_leader_reset_reignition import install as install_gs477

    install_gs477()


def final_enriched_opportunity_records(
    records: list[dict], *, actionable_function=None
) -> list[dict]:
    """Build the complete enriched presentation collection, then sort it once."""
    from . import ui
    from .gs369_escalation_priority_order import ordered_escalation_records
    from .gs477_leader_reset_reignition import enrich_visible_records

    actionable = actionable_function or ui.actionable_candidate_records
    # GS477 operates on a detached snapshot here instead of permanently wrapping the
    # public actionable callable. That preserves GS414's exact restoration invariant.
    enriched = enrich_visible_records(list(records or []), actionable)
    return ordered_escalation_records(enriched)


def install() -> None:
    """Freeze final enrichment/order across the complete Opportunity State render."""
    from . import ui

    # GS475 is data-truth only and must bind before any live provider snapshot can be
    # consumed. GS391 lives inside the legacy late chain; reassert GS464 next so all
    # subsequent evidence/presentation layers see the same session-aware primary VWAP
    # authority. GS465 remains the final card-order contract; GS466 changes only
    # visibility of awareness-only current extremes; GS467 adjudicates standalone 1m
    # urgency; GS468 enforces numeric VWAP truth; GS474 enforces LOOK NOW freshness;
    # GS477 then adds bounded leader-reset state/audio without trading authority.
    _install_gs475()
    _install_gs464()
    _install_gs462()
    _install_gs463()
    _install_gs465()
    _install_gs466()
    _install_gs467()
    _install_gs468()
    _install_gs474()
    _install_gs477()

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

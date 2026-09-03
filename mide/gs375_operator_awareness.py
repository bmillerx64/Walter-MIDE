"""GS375: separate market awareness from entry eligibility on Walter's live screen.

Live validation on 2026-09-03 showed the opposite failure mode from stale-card
pollution: current Webull leaders could disappear entirely once they failed the
scanner's watch/entry qualification, even though they still deserved operator
attention.  That made an opportunity-rich tape look artificially empty.

This module reuses GS309's existing *current attention* provenance as the only
awareness criterion.  It does not invent a new market threshold.  Records that
are current DAY_GAINERS, fresh news seeds, fresh re-ignitions, fresh volume-regime
promotions, or halts may remain visible even when ``qualified_for_watch`` is false.
They are tagged ``operator_awareness_only`` and explicitly denied entry/alert
authorization.

GS373's freshness and far-below-VWAP visibility filter remains authoritative, so
stale or structurally irrelevant records still stay off the operator screen.
Awareness-only records can render as LOOK NOW, DEVELOPING, CHASE / WAIT, or HALTED,
but can never render as WATCH FOR ENTRY merely because display evidence aligns.

Scanner discovery, scoring, ranking, qualification, trigger thresholds, readiness,
execution, and orders are unchanged.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Callable

AWARENESS_ONLY_KEY = "operator_awareness_only"


def operator_awareness_eligible(record: dict) -> bool:
    """Return whether a non-actionable record still deserves live operator awareness."""
    from .gs309_current_attention_mission import current_attention_provenance
    from .gs373_operator_visibility_freshness import operator_visible

    return operator_visible(record) and bool(current_attention_provenance(record))


def awareness_record(record: dict) -> dict:
    """Return a presentation copy that cannot acquire trade authorization."""
    row = deepcopy(record)
    row[AWARENESS_ONLY_KEY] = True
    row["qualified_for_entry"] = False
    row["qualified_for_alert"] = False
    row["advanced_state"] = False
    row["entered_watchlist"] = False
    return row


def augment_operator_records(records: list[dict], actionable: list[dict]) -> list[dict]:
    """Add current-attention leaders to the visible workflow without changing source rows."""
    output = list(actionable or [])
    present = {
        str(record.get("symbol") or "").strip().upper()
        for record in output
        if str(record.get("symbol") or "").strip()
    }
    for record in records or []:
        symbol = str(record.get("symbol") or "").strip().upper()
        if not symbol or symbol in present:
            continue
        if not operator_awareness_eligible(record):
            continue
        output.append(awareness_record(record))
        present.add(symbol)
    return output


def awareness_safe_opportunity_state(
    record: dict,
    state_function: Callable[[dict], dict] | None = None,
) -> dict:
    """Clamp display-only awareness so it never masquerades as entry permission."""
    from . import gs310_unified_opportunity_state as unified

    original = state_function or getattr(
        unified.opportunity_state, "_gs375_original", unified.opportunity_state
    )
    view = deepcopy(original(record))
    if not record.get(AWARENESS_ONLY_KEY):
        return view

    if view.get("state") == unified.WATCH_FOR_ENTRY:
        view["state"] = unified.LOOK_NOW
        view["color"] = unified.STATE_COLORS[unified.LOOK_NOW]
        view["reason"] = (
            "Current market-attention leader, but scanner watch/entry qualification "
            "is not complete."
        )
        view["next_step"] = (
            "Keep the chart open; entry remains locked until Walter's scanner "
            "qualification and trigger rules are satisfied."
        )
    elif view.get("state") in {unified.LOOK_NOW, unified.DEVELOPING}:
        original_reason = str(view.get("reason") or "").strip()
        view["reason"] = (
            "Current market-attention leader; not yet scanner-qualified for entry review."
            + (f" {original_reason}" if original_reason else "")
        )
        view["next_step"] = (
            "Keep it visible and reassess current VWAP, SuperTrend, participation, "
            "and expansion; entry remains locked until scanner qualification completes."
        )
    return view


def _inherit(wrapper, wrapped) -> None:
    for name, value in getattr(wrapped, "__dict__", {}).items():
        if name.startswith("_gs") and not hasattr(wrapper, name):
            setattr(wrapper, name, value)


def install() -> None:
    """Install the awareness layer before app.py binds UI callables by name."""
    from . import ui
    from . import gs310_unified_opportunity_state as unified

    current_records = ui.actionable_candidate_records
    if not getattr(current_records, "_gs375_operator_awareness", False):
        original_records = current_records

        def operator_records(records: list[dict]) -> list[dict]:
            return augment_operator_records(records, original_records(records))

        _inherit(operator_records, original_records)
        operator_records._gs375_operator_awareness = True
        operator_records._gs375_original = original_records
        ui.actionable_candidate_records = operator_records

    current_state = unified.opportunity_state
    if not getattr(current_state, "_gs375_operator_awareness", False):
        original_state = current_state

        def safe_state(record: dict) -> dict:
            return awareness_safe_opportunity_state(record, original_state)

        _inherit(safe_state, original_state)
        safe_state._gs375_operator_awareness = True
        safe_state._gs375_original = original_state
        unified.opportunity_state = safe_state

        # Several presentation/voice modules imported the function object directly
        # before startup.py runs. Rebind those already-loaded aliases so every live
        # surface honors the same awareness-vs-entry safety clamp.
        for module_name in (
            "gs311_unified_voice",
            "gs314_state_consistency",
            "gs363_operator_attention_hierarchy",
        ):
            try:
                module = __import__(f"mide.{module_name}", fromlist=[module_name])
                if getattr(module, "opportunity_state", None) is original_state:
                    module.opportunity_state = safe_state
            except Exception:
                continue

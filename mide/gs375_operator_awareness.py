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
REFERENCE_DATA_BLOCKED_KEY = "reference_data_blocked_awareness"
FIVE_MINUTE_MOVER_REASON = "Webull native: five_minute_movers"
DAY_GAINER_REASON = "Webull native: day_gainers"
REFERENCE_DATA_MOVER_REASONS = {
    FIVE_MINUTE_MOVER_REASON,
    DAY_GAINER_REASON,
}


def reference_data_blocked_mover(record: dict) -> bool:
    """Keep a current native mover visible when float authority is unresolved, not failed."""
    if str(record.get("terminal_stage") or "") != "Free-Float Gate":
        return False
    if str(record.get("terminal_outcome") or "").strip().lower() != "rejected":
        return False
    if record.get("free_float_verified") is not False:
        return False

    reasons = {str(value or "").strip() for value in record.get("discovery_reasons") or []}
    if not reasons.intersection(REFERENCE_DATA_MOVER_REASONS):
        return False

    status = str(record.get("free_float_verification_status") or "").strip().lower()
    source = str(record.get("free_float_source") or "").strip().lower()
    unresolved = status in {"refresh-unavailable-reject", "unavailable-reject"} or (
        "unresolved" in source and "fail closed" in source
    )
    return unresolved


def operator_awareness_eligible(record: dict) -> bool:
    """Return whether a non-actionable record still deserves live operator awareness."""
    from .gs309_current_attention_mission import current_attention_provenance
    from .gs373_operator_visibility_freshness import operator_visible

    if not operator_visible(record):
        return False
    return bool(
        current_attention_provenance(record)
        or reference_data_blocked_mover(record)
    )


def awareness_record(record: dict) -> dict:
    """Return a presentation copy that cannot acquire trade authorization."""
    row = deepcopy(record)
    row[AWARENESS_ONLY_KEY] = True
    if reference_data_blocked_mover(record):
        row[REFERENCE_DATA_BLOCKED_KEY] = True
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


def _near_above_current_attention(record: dict) -> bool:
    """Return whether a current-attention row belongs in LOOK NOW rather than DEVELOPING.

    This deliberately resolves only presentation state.  It is independent of the
    scanner's watch/entry qualification and makes the result stable even when a warm
    Streamlit/test runtime still holds an older GS310 wrapper that would otherwise
    classify the same row as DEVELOPING.
    """
    from .gs309_current_attention_mission import current_attention_provenance

    relation = str(record.get("vwap_relation") or "").lower()
    if relation != "above":
        return False
    try:
        distance = float(record.get("vwap_distance_pct"))
    except (TypeError, ValueError):
        distance = None
    if distance is not None and distance > 2.0:
        return False
    return bool(current_attention_provenance(record))


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

    state = view.get("state")
    if record.get(REFERENCE_DATA_BLOCKED_KEY):
        if state == unified.HALTED:
            return view
        view["state"] = unified.LOOK_NOW
        view["color"] = unified.STATE_COLORS[unified.LOOK_NOW]
        view["reason"] = (
            "Current Webull mover, but free-float reference data is unresolved. "
            "This is awareness only; entry remains locked."
        )
        view["next_step"] = (
            "Open the chart now for awareness. Walter cannot rank or authorize entry "
            "unless a later scan resolves the Free-Float Gate."
        )
        evidence = list(view.get("evidence") or [])
        evidence.append(
            {
                "label": "Reference Data",
                "passed": False,
                "detail": "Free float unresolved · entry locked",
            }
        )
        view["evidence"] = evidence
        return view

    force_look_now = bool(
        state == unified.WATCH_FOR_ENTRY
        or (
            state in {unified.LOOK_NOW, unified.DEVELOPING}
            and _near_above_current_attention(record)
        )
    )
    if force_look_now:
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
    elif state in {unified.LOOK_NOW, unified.DEVELOPING}:
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

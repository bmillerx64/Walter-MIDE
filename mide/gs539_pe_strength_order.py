"""GS539: make Opportunity State card order match visible Participation/Expansion strength.

Sept. 23 live validation showed two operator problems at once:
* a green WATCH FOR ENTRY card (EDVA, Participation 85 / Expansion 62) rendered below
  an orange CHASE / WAIT card (AVAT, Participation 32 / Expansion 63); and
* the final GS414 freeze owned render_escalation_engine, while GS332 routes the live
  Opportunity State surface through render_walter_mission_control.

GS539 makes the visible ordering contract explicit and easy to audit:
* canonical ENTRY READY (qualified_for_entry=True) remains absolute first;
* HALTED remains last;
* every other card is ordered by P/E Strength = mean(Participation, Expansion),
  descending. This is equivalent to sorting by their sum when both are 0-100.
* color/state remains structural context only; it no longer silently determines the
  vertical order.

Presentation only. No discovery, provider calls, scores, gates, thresholds, readiness,
anti-chase, alert truth, execution, cadence, or orders change.
"""
from __future__ import annotations

from copy import deepcopy
from functools import wraps
from typing import Any, Callable, Iterable

_OWNER_ORDER = "_walter_gs539_pe_strength_order_owner"
_OWNER_STATE = "_walter_gs539_pe_strength_state_owner"


def _number(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def participation_value(record: dict) -> float | None:
    for key in ("participation_surge_score", "participation_score"):
        value = _number(record.get(key))
        if value is not None:
            return value
    return None


def expansion_value(record: dict) -> float | None:
    for key in ("expansion_quality", "expansion_score"):
        value = _number(record.get(key))
        if value is not None:
            return value
    return None


def pe_strength_score(record: dict) -> float | None:
    """Return the visible 0-100 mean of Participation and Expansion."""
    participation = participation_value(record)
    expansion = expansion_value(record)
    if participation is None or expansion is None:
        return None
    return (participation + expansion) / 2.0


def _halted(record: dict) -> bool:
    if any(record.get(key) is True for key in ("halted", "is_halted", "suspended", "is_suspended")):
        return True
    text = " ".join(
        str(record.get(key) or "")
        for key in ("halt_status", "trading_status", "market_status", "status_reason")
    ).casefold()
    return "halt" in text or "suspend" in text


def ordered_pe_strength_records(
    records: Iterable[dict],
    *,
    baseline_order: Callable[[list[dict]], list[dict]] | None = None,
) -> list[dict]:
    """Keep existing tie behavior but make P/E Strength the visible primary order."""
    source = list(records or [])
    rows = list(baseline_order(source) if baseline_order is not None else source)

    # Stable passes: prior canonical ordering survives exact P/E ties.
    rows.sort(
        key=lambda record: (
            pe_strength_score(record)
            if pe_strength_score(record) is not None
            else float("-inf")
        ),
        reverse=True,
    )
    # Executable truth outranks presentation strength.
    rows.sort(key=lambda record: bool(record.get("qualified_for_entry") is True), reverse=True)
    # A halt is important awareness, but not a working setup in the card stack.
    rows.sort(key=_halted)
    return rows


def state_with_pe_strength(original, record: dict) -> dict:
    """Explain the ordering number without changing Opportunity State/color."""
    view = original(record)
    score = pe_strength_score(record)
    if score is None:
        return view
    result = deepcopy(view)
    result["pe_strength_score"] = round(score, 1)
    reason = str(result.get("reason") or "").strip()
    prefix = f"P/E Strength {score:.0f}/100"
    if not reason.startswith("P/E Strength "):
        result["reason"] = f"{prefix} · {reason}".strip(" ·")
    return result


def _inherit(wrapper, wrapped) -> None:
    for name, value in getattr(wrapped, "__dict__", {}).items():
        if name.startswith("_gs") and not hasattr(wrapper, name):
            setattr(wrapper, name, value)


def install() -> None:
    """Bind after GS528 so state labels are final before presentation sorting."""
    from . import gs310_unified_opportunity_state as unified
    from . import gs311_unified_voice as voice
    from . import gs314_state_consistency as consistency
    from . import gs363_operator_attention_hierarchy as hierarchy
    from . import gs369_escalation_priority_order as gs369

    current_state = unified.opportunity_state
    if getattr(current_state, _OWNER_STATE, False):
        calibrated = current_state
    else:
        @wraps(current_state)
        def calibrated(record: dict) -> dict:
            return state_with_pe_strength(current_state, record)

        _inherit(calibrated, current_state)
        calibrated._gs539_pe_strength_order = True
        calibrated._gs539_original = current_state
        setattr(calibrated, _OWNER_STATE, True)
        unified.opportunity_state = calibrated

    voice.opportunity_state = calibrated
    consistency.opportunity_state = calibrated
    hierarchy.opportunity_state = calibrated

    current_order = gs369.ordered_escalation_records
    if getattr(current_order, _OWNER_ORDER, False):
        return

    def ordered_escalation_records(records: list[dict]) -> list[dict]:
        return ordered_pe_strength_records(records, baseline_order=current_order)

    _inherit(ordered_escalation_records, current_order)
    ordered_escalation_records._gs539_pe_strength_order = True
    ordered_escalation_records._gs539_original = current_order
    setattr(ordered_escalation_records, _OWNER_ORDER, True)
    gs369.ordered_escalation_records = ordered_escalation_records

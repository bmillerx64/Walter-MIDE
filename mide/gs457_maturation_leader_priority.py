"""GS457: keep recent ST/VWAP maturation leaders high in operator priority.

Live validation after GS455/GS456 showed one remaining presentation/ranking gap.
Walter correctly creates a short-lived LOOK NOW pulse when a new 30s -> 1m -> 3m ->
5m+ ST/VWAP crossover rung appears. But once that "new" window expires, an extended
leader falls back to ordinary CHASE / WAIT. The canonical operator hierarchy then
places every DEVELOPING symbol above it, even when the leader still has a recent,
ordered, currently-confirmed 3m/5m+ crossover sequence and supporting flow.

GS457 does not loosen discovery, participation, expansion, qualification, readiness,
entry, execution, or anti-chase rules. It changes only operator ordering:

* WATCH FOR ENTRY remains highest.
* A currently-active GS455 maturation pulse ranks next, even when anti-chase keeps the
  visible state at CHASE / WAIT.
* Ordinary LOOK NOW remains next.
* A recent, ordered, currently-confirmed 3m+ maturation sequence with GS455's existing
  supporting-flow evidence ranks above ordinary DEVELOPING while it remains recent.
* Ordinary DEVELOPING, CHASE / WAIT, and HALTED retain their established order.

The card's state is never rewritten. An extended leader can therefore move up the
screen while still saying CHASE / WAIT / DO NOT CHASE.
"""
from __future__ import annotations

from typing import Any

FRESH_MATURATION_BAND = 45
LOOK_NOW_BAND = 40
RECENT_CONFIRMATION_BAND = 35
DEVELOPING_BAND = 30
CHASE_WAIT_BAND = 20
HALTED_BAND = 10
WATCH_FOR_ENTRY_BAND = 50

_HIGHER_CONFIRMATION_RUNGS = ("3m", "5m", "10m", "15m")
_OWNER_ATTR = "_walter_gs457_maturation_leader_priority_owner"


def _number(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number


def maturation_attention(record: dict) -> dict:
    """Return presentation-only maturation priority details for one record."""
    from . import gs310_unified_opportunity_state as unified
    from . import gs455_early_ignition_3m_confirmation as gs455

    view = unified.opportunity_state(record)
    state = str(view.get("state") or "")
    progression = gs455.crossover_progression(record)
    signal = gs455.progression_signal(record)

    events = progression.get("events") or {}
    active = list(progression.get("active_rungs") or [])
    recent_higher: list[str] = []
    for label in _HIGHER_CONFIRMATION_RUNGS:
        if label not in active:
            continue
        event = dict(events.get(label) or {})
        if (
            event.get("recent")
            and event.get("current_confirmed")
            and event.get("crossed")
        ):
            recent_higher.append(label)

    supporting_flow = bool(gs455._supporting_flow(record))
    sustained_confirmation = bool(
        progression.get("ordered")
        and recent_higher
        and supporting_flow
        and state != unified.HALTED
    )
    fresh_maturation = bool(
        signal.get("active")
        and state != unified.HALTED
        and state != unified.WATCH_FOR_ENTRY
    )

    if state == unified.WATCH_FOR_ENTRY:
        band = WATCH_FOR_ENTRY_BAND
        reason = "watch_for_entry"
    elif fresh_maturation:
        band = FRESH_MATURATION_BAND
        reason = "fresh_maturation"
    elif state == unified.LOOK_NOW:
        band = LOOK_NOW_BAND
        reason = "look_now"
    elif sustained_confirmation:
        band = RECENT_CONFIRMATION_BAND
        reason = "recent_3m_plus_confirmation"
    elif state == unified.DEVELOPING:
        band = DEVELOPING_BAND
        reason = "developing"
    elif state == unified.CHASE_WAIT:
        band = CHASE_WAIT_BAND
        reason = "chase_wait"
    else:
        band = HALTED_BAND
        reason = "halted_or_other"

    highest_recent = recent_higher[-1] if recent_higher else None
    latest_new = progression.get("latest_new_rung")
    priority_rung = latest_new or highest_recent
    rung_rank = (
        gs455.CROSSOVER_LADDER.index(priority_rung) + 1
        if priority_rung in gs455.CROSSOVER_LADDER
        else 0
    )

    event = dict(events.get(priority_rung) or {}) if priority_rung else {}
    age = _number(event.get("age_seconds"))
    freshness = -age if age is not None else float("-inf")

    return {
        "band": band,
        "reason": reason,
        "state": state,
        "fresh_maturation": fresh_maturation,
        "sustained_confirmation": sustained_confirmation,
        "recent_higher_rungs": recent_higher,
        "priority_rung": priority_rung,
        "rung_rank": rung_rank,
        "freshness": freshness,
        "progression_stage": progression.get("stage"),
        "progression_sequence": progression.get("sequence") or "",
        "supporting_flow": supporting_flow,
    }


def maturation_priority_sort_key(record: dict) -> tuple:
    """Return the final presentation key while preserving existing tie-breakers."""
    from . import ui
    from .gs363_operator_attention_hierarchy import operator_attention_score

    attention = maturation_attention(record)
    try:
        established = ui.trader_priority_sort_key(record)
    except Exception:
        established = ()
    return (
        int(attention["band"]),
        int(attention["rung_rank"]),
        float(attention["freshness"]),
        int(operator_attention_score(record)),
        established,
        str(record.get("symbol") or "").upper(),
    )


def ordered_maturation_records(records: list[dict]) -> list[dict]:
    """Order operator cards without changing candidate membership or state."""
    rows = list(records or [])
    return sorted(rows, key=maturation_priority_sort_key, reverse=True)


def install() -> None:
    """Hard-bind GS457 at Walter's final late-runtime ordering boundary."""
    from . import gs369_escalation_priority_order as gs369

    current = gs369.ordered_escalation_records
    if getattr(current, _OWNER_ATTR, False):
        return

    def ordered_escalation_records(records: list[dict]) -> list[dict]:
        return ordered_maturation_records(records)

    for name, value in getattr(current, "__dict__", {}).items():
        if name.startswith("_gs") and not hasattr(ordered_escalation_records, name):
            setattr(ordered_escalation_records, name, value)

    ordered_escalation_records._gs457_maturation_leader_priority = True
    ordered_escalation_records._gs457_original = current
    setattr(ordered_escalation_records, _OWNER_ATTR, True)
    gs369.ordered_escalation_records = ordered_escalation_records

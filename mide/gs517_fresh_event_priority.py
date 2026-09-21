"""GS517: restore fresh maturation events above static Mission Ranking.

Sep. 21 live validation exposed a narrow conflict between two correct contracts.
GS457 makes a newly reached ordered ST/VWAP maturation rung an immediate operator
attention event. GS497 later makes current Mission Ranking primary for every ranked
non-entry record. In the live XTIA/SDST case, that allowed a relatively static ranked
LOOK NOW row to render above XTIA while XTIA was actively maturing through 1m and
accelerating.

GS517 restores event recency at the final operator-order boundary:

* WATCH FOR ENTRY remains absolute first.
* A current GS455 fresh maturation signal comes next, regardless of Mission Rank.
* All other non-entry rows keep GS497's exact Mission Rank / fallback order.
* HALTED remains absolute last.

This is presentation ordering only. It does not change discovery, Mission Ranking,
scores, participation, expansion, VWAP/SuperTrend truth, qualification, readiness,
anti-chase state, alert truth, execution, or orders. Because the existing audio layer
consumes Walter's incoming operator order, the same correction naturally makes the
freshest maturation event win attention audio without creating a new alert.
"""
from __future__ import annotations

from collections.abc import Callable, Iterable


_OWNER_ATTR = "_walter_gs517_fresh_event_priority_owner"


def fresh_maturation_event(record: dict) -> bool:
    """Return current GS455 maturation-event truth without inventing new thresholds."""
    from . import gs310_unified_opportunity_state as unified
    from . import gs455_early_ignition_3m_confirmation as gs455

    try:
        state = str(unified.opportunity_state(record).get("state") or "")
    except Exception:
        state = ""
    if state in {unified.WATCH_FOR_ENTRY, unified.HALTED}:
        return False
    try:
        return bool(gs455.progression_signal(record).get("active"))
    except Exception:
        return False


def ordered_fresh_event_records(
    records: Iterable[dict],
    *,
    baseline_order: Callable[[list[dict]], list[dict]] | None = None,
) -> list[dict]:
    """Lift only fresh maturation events above GS497's otherwise-authoritative order."""
    from . import gs310_unified_opportunity_state as unified

    source = list(records or [])
    rows = list(baseline_order(source) if baseline_order is not None else source)

    def attention_band(record: dict) -> int:
        try:
            state = str(unified.opportunity_state(record).get("state") or "")
        except Exception:
            state = ""
        if state == unified.WATCH_FOR_ENTRY:
            return 3
        if state == unified.HALTED:
            return 0
        if fresh_maturation_event(record):
            return 2
        return 1

    # Stable sort: within each band, preserve GS497 exactly, including Mission Rank.
    rows.sort(key=attention_band, reverse=True)
    return rows


def _inherit(wrapper, wrapped) -> None:
    for name, value in getattr(wrapped, "__dict__", {}).items():
        if name.startswith("_gs") and not hasattr(wrapper, name):
            setattr(wrapper, name, value)


def install() -> None:
    """Bind immediately outside GS497 at the final enriched Opportunity boundary."""
    from . import gs369_escalation_priority_order as gs369

    current = gs369.ordered_escalation_records
    if getattr(current, _OWNER_ATTR, False):
        return

    def ordered_escalation_records(records: list[dict]) -> list[dict]:
        return ordered_fresh_event_records(records, baseline_order=current)

    _inherit(ordered_escalation_records, current)
    ordered_escalation_records._gs517_fresh_event_priority = True
    ordered_escalation_records._gs517_original = current
    setattr(ordered_escalation_records, _OWNER_ATTR, True)
    gs369.ordered_escalation_records = ordered_escalation_records

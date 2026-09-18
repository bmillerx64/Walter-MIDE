"""GS497: let canonical Mission Ranking own operator priority below entry-ready.

Sept. 18 post-reboot validation isolated the late-session attention mismatch without
needing a new trading or persistence rule. NCRA and ZTG were both discovered,
snapshotted, qualified for ranking, and shown in the actionable display on the same
scan. Walter already ranked ZTG #2 with leader-class move/flow evidence while NCRA was
ranked #11, yet GS465's strict state-first presentation put NCRA's fresh LOOK NOW above
ZTG's truthful CHASE / WAIT.

The failure is therefore final presentation ordering, not discovery, snapshot loss,
qualification, anti-chase, or missing leader evidence. Mission Ranking had already
made the relative-priority decision; the final Opportunity State stack discarded it.

GS497 keeps WATCH FOR ENTRY absolute first and HALTED absolute last. For every other
currently ranked record, canonical mission_rank becomes the primary operator priority.
Opportunity State remains visible and unchanged, so an extended leader can sit at the
front while still saying CHASE / WAIT / DO NOT CHASE. Records without a current
Mission Ranking fall back to GS465's established state-contiguous ordering.

Presentation ordering only. No discovery, provider request, market-data value,
indicator, VWAP/ST threshold, participation, expansion, score, qualification,
readiness, alert truth, execution, cadence, or order behavior changes.
"""
from __future__ import annotations

from typing import Callable, Iterable


_OWNER_ATTR = "_walter_gs497_rank_aware_attention_order_owner"


def current_mission_rank(record: dict) -> int | None:
    """Return a current positive Mission Ranking, rejecting stale terminal residue."""
    value = record.get("mission_rank")
    try:
        rank = int(float(value))
    except (TypeError, ValueError):
        return None
    if rank <= 0:
        return None

    terminal_stage = str(record.get("terminal_stage") or "").strip()
    terminal_outcome = str(record.get("terminal_outcome") or "").strip().lower()

    if terminal_stage and terminal_stage != "Mission Ranking and Publication":
        return None
    if terminal_outcome and "ranked" not in terminal_outcome:
        return None
    return rank


def ordered_rank_aware_records(
    records: Iterable[dict],
    *,
    baseline_order: Callable[[list[dict]], list[dict]] | None = None,
) -> list[dict]:
    """Honor Mission Ranking below WATCH FOR ENTRY while preserving state semantics."""
    from . import gs310_unified_opportunity_state as unified

    source = list(records or [])
    rows = list(baseline_order(source) if baseline_order is not None else source)

    ready: list[dict] = []
    ranked: list[dict] = []
    unranked: list[dict] = []
    halted: list[dict] = []

    for record in rows:
        try:
            state = str(unified.opportunity_state(record).get("state") or "")
        except Exception:
            state = ""
        if state == unified.WATCH_FOR_ENTRY:
            ready.append(record)
        elif state == unified.HALTED:
            halted.append(record)
        elif current_mission_rank(record) is not None:
            ranked.append(record)
        else:
            unranked.append(record)

    ranked.sort(key=lambda record: current_mission_rank(record) or 10**9)
    return ready + ranked + unranked + halted


def _inherit(wrapper, wrapped) -> None:
    for name, value in getattr(wrapped, "__dict__", {}).items():
        if name.startswith("_gs") and not hasattr(wrapper, name):
            setattr(wrapper, name, value)


def install() -> None:
    """Install rank-aware operator ordering after GS465's semantic cleanup."""
    from . import gs369_escalation_priority_order as gs369

    current = gs369.ordered_escalation_records
    if getattr(current, _OWNER_ATTR, False):
        return

    def ordered_escalation_records(records: list[dict]) -> list[dict]:
        return ordered_rank_aware_records(records, baseline_order=current)

    _inherit(ordered_escalation_records, current)
    ordered_escalation_records._gs497_rank_aware_attention_order = True
    ordered_escalation_records._gs497_original = current
    setattr(ordered_escalation_records, _OWNER_ATTR, True)
    gs369.ordered_escalation_records = ordered_escalation_records

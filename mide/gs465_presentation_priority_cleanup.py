"""GS465: make Walter's visible priority language internally consistent.

Live validation on 2026-09-16 exposed two presentation contradictions:

* GS333 could label a +75% current mover ``EXTREME MOVER · LOOK NOW`` merely because
  it was not more than 5% above VWAP. That label could therefore mean "large move"
  rather than "current structure has earned immediate chart review".
* GS463 deliberately let attention-only ignition/maturation lifts cross Opportunity
  State boundaries. A CHASE / WAIT card with an attention lift could consequently
  render above DEVELOPING, producing visually alternating CHASE / WAIT -> DEVELOPING
  -> CHASE / WAIT stacks even though every individual card was truthful.

GS465 separates those jobs cleanly:

1. The Opportunity State card stack is state-first and contiguous:
   WATCH FOR ENTRY > LOOK NOW > DEVELOPING > CHASE / WAIT > HALTED/other.
   Ignition/maturation/trajectory evidence remains useful only as a tie-breaker
   *within the same state*.
2. An extreme mover no longer earns the words LOOK NOW from percentage move alone.
   Near-VWAP extremes become ``EXTREME MOVER · WATCH`` unless the current unified
   state independently earned LOOK NOW through a specific structural reason. A real
   WATCH FOR ENTRY remains labeled as such.
3. GS443's multi-leader continuity is preserved. If several generic extreme WATCH
   names exist and no non-extreme actionable setup deserves the top sightline, one
   still owns the single market-event banner so the others can remain visible in the
   watch-only Market Leader Radar. That ownership does not promote the symbol to
   LOOK NOW or grant any trading authority.

This module is presentation-only. It changes no discovery membership, provider
request, indicator formula, VWAP/ST threshold, qualification, readiness, alert
permission, execution rule, or order behavior.
"""
from __future__ import annotations

from functools import wraps

from .authorities import presentation_audio as _presentation

_ORDER_OWNER_ATTR = "_walter_gs465_state_contiguous_order_owner"
_EXTREME_OWNER_ATTR = "_walter_gs465_extreme_semantics_owner"
_EXTREME_SELECTION_OWNER_ATTR = "_walter_gs465_extreme_selection_continuity_owner"

WATCH_FOR_ENTRY_BAND = _presentation.CONTIGUOUS_WATCH_FOR_ENTRY_BAND
LOOK_NOW_BAND = _presentation.CONTIGUOUS_LOOK_NOW_BAND
DEVELOPING_BAND = _presentation.CONTIGUOUS_DEVELOPING_BAND
CHASE_WAIT_BAND = _presentation.CONTIGUOUS_CHASE_WAIT_BAND
HALTED_BAND = _presentation.CONTIGUOUS_HALTED_BAND
OTHER_BAND = _presentation.CONTIGUOUS_OTHER_BAND


def strict_state_band(record: dict) -> int:
    return _presentation.strict_state_band(record)


def attention_tiebreak(record: dict) -> tuple[int, float, float]:
    return _presentation.attention_tiebreak(record)


def ordered_state_contiguous_records(records: list[dict], baseline_order=None) -> list[dict]:
    return _presentation.ordered_state_contiguous_records(
        records,
        baseline_order=baseline_order,
    )


def _specific_look_now(view: dict) -> bool:
    """Distinguish structural LOOK NOW from generic market-attention LOOK NOW."""
    from . import gs310_unified_opportunity_state as unified

    if str(view.get("state") or "") != unified.LOOK_NOW:
        return False
    reason = str(view.get("reason") or "").strip().lower()
    generic = (
        "a current attention trigger says this symbol deserves a chart review",
        "current market-attention leader",
    )
    return bool(reason and not any(text in reason for text in generic))


def cleaned_extreme_event(original, record: dict) -> dict | None:
    return _presentation.cleaned_extreme_event(original, record)


def _non_extreme_actionable_symbols(rows: list[dict], extreme_symbols: set[str]) -> set[str]:
    """Return actual setup symbols that should make a generic extreme WATCH yield."""
    from . import gs310_unified_opportunity_state as unified

    priority_states = {
        unified.WATCH_FOR_ENTRY,
        unified.LOOK_NOW,
        unified.DEVELOPING,
    }
    symbols: set[str] = set()
    for record in rows:
        symbol = str(record.get("symbol") or "").strip().upper()
        if not symbol or symbol in extreme_symbols:
            continue
        try:
            state = str(unified.opportunity_state(record).get("state") or "")
        except Exception:
            continue
        if state in priority_states:
            symbols.add(symbol)
    return symbols


def prioritized_extreme_with_watch_continuity(original, records, *, now=None):
    return _presentation.prioritized_extreme_with_watch_continuity(
        original,
        records,
        now=now,
    )


def _inherit(wrapper, wrapped) -> None:
    for name, value in getattr(wrapped, "__dict__", {}).items():
        if name.startswith("_gs") and not hasattr(wrapper, name):
            setattr(wrapper, name, value)


def _install_order() -> None:
    _presentation.activate_operator_order_stage("state_contiguous")


def _install_extreme_semantics() -> None:
    _presentation.activate_extreme_event_stage("cleanup")


def _install_extreme_selection_continuity() -> None:
    _presentation.install_extreme_selection_continuity()


def install() -> None:
    """Install final visible card ordering plus truthful extreme-mover language."""
    _install_order()
    _install_extreme_semantics()
    _install_extreme_selection_continuity()

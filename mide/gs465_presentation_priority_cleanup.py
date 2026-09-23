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
    """Keep extreme-mover awareness without manufacturing LOOK NOW semantics."""
    from . import gs310_unified_opportunity_state as unified

    event = original(record)
    if not event:
        return event
    if event.get("halted") or "DO NOT CHASE" in str(event.get("label") or "").upper():
        return event

    try:
        view = unified.opportunity_state(record)
    except Exception:
        view = {}
    state = str(view.get("state") or "")

    cleaned = dict(event)
    if state == unified.WATCH_FOR_ENTRY:
        cleaned["label"] = "EXTREME MOVER · WATCH FOR ENTRY"
        cleaned["guidance"] = (
            "The normal opportunity state has earned WATCH FOR ENTRY. Use the same "
            "entry evidence and risk discipline as any other setup."
        )
    elif _specific_look_now(view):
        cleaned["label"] = "EXTREME MOVER · LOOK NOW"
        cleaned["guidance"] = (
            "Current structure independently earned LOOK NOW; the large percentage "
            "move is context, not the reason for urgency."
        )
    else:
        cleaned["label"] = "EXTREME MOVER · WATCH"
        cleaned["guidance"] = (
            "Major mover worth monitoring, but the current structure has not earned "
            "LOOK NOW. Let normal VWAP/ST/ignition evidence promote it."
        )
    return cleaned


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
    """Preserve GS443 single-banner ownership for generic extreme WATCH names.

    The established selector keeps authority for HALTED, structural LOOK NOW and
    DO-NOT-CHASE decay semantics. This fallback runs only when that selector returns
    no event, and only for plain ``EXTREME MOVER · WATCH`` records. It therefore
    restores multi-extreme de-duplication without reviving the old fake LOOK NOW.
    """
    from . import gs333_extreme_mover_operator_priority as extreme

    rows = list(records or [])
    if now is None:
        selected = original(rows)
    else:
        try:
            selected = original(rows, now=now)
        except TypeError:
            selected = original(rows)
    if selected and selected[0] is not None:
        return selected

    events: list[tuple[dict, dict]] = []
    extreme_symbols: set[str] = set()
    for record in rows:
        event = extreme.extreme_market_event(record)
        if not event:
            continue
        symbol = str(event.get("symbol") or record.get("symbol") or "").strip().upper()
        if symbol:
            extreme_symbols.add(symbol)
        events.append((record, event))

    # A real non-extreme WATCH/LOOK/DEVELOPING setup owns the action-first sightline.
    if _non_extreme_actionable_symbols(rows, extreme_symbols):
        return None, None

    choices: list[tuple[tuple[float, float], dict, dict]] = []
    for record, event in events:
        if str(event.get("label") or "").upper() != "EXTREME MOVER · WATCH":
            continue
        try:
            pct_change = float(event.get("pct_change") or 0.0)
        except (TypeError, ValueError):
            pct_change = 0.0
        try:
            dollar_volume = float(record.get("dollar_volume") or 0.0)
        except (TypeError, ValueError):
            dollar_volume = 0.0
        choices.append(((pct_change, dollar_volume), record, event))

    if not choices:
        return None, None
    _, record, event = max(choices, key=lambda item: item[0])
    return record, event


def _inherit(wrapper, wrapped) -> None:
    for name, value in getattr(wrapped, "__dict__", {}).items():
        if name.startswith("_gs") and not hasattr(wrapper, name):
            setattr(wrapper, name, value)


def _install_order() -> None:
    _presentation.activate_operator_order_stage("state_contiguous")


def _install_extreme_semantics() -> None:
    from . import gs333_extreme_mover_operator_priority as extreme

    current = extreme.extreme_market_event
    if getattr(current, _EXTREME_OWNER_ATTR, False):
        return

    @wraps(current)
    def extreme_market_event(record: dict) -> dict | None:
        return cleaned_extreme_event(current, record)

    _inherit(extreme_market_event, current)
    extreme_market_event._gs465_presentation_priority_cleanup = True
    extreme_market_event._gs465_original = current
    setattr(extreme_market_event, _EXTREME_OWNER_ATTR, True)
    extreme.extreme_market_event = extreme_market_event


def _install_extreme_selection_continuity() -> None:
    from . import gs333_extreme_mover_operator_priority as extreme

    current = extreme.prioritized_extreme_event
    if getattr(current, _EXTREME_SELECTION_OWNER_ATTR, False):
        return

    @wraps(current)
    def prioritized_extreme_event(records, *, now=None):
        return prioritized_extreme_with_watch_continuity(current, records, now=now)

    _inherit(prioritized_extreme_event, current)
    prioritized_extreme_event._gs465_presentation_priority_cleanup = True
    prioritized_extreme_event._gs465_original = current
    setattr(prioritized_extreme_event, _EXTREME_SELECTION_OWNER_ATTR, True)
    extreme.prioritized_extreme_event = prioritized_extreme_event


def install() -> None:
    """Install final visible card ordering plus truthful extreme-mover language."""
    _install_order()
    _install_extreme_semantics()
    _install_extreme_selection_continuity()

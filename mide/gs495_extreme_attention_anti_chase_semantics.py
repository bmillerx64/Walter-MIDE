"""GS495: keep extreme-mover attention loud while making anti-chase explicit.

Sep. 18 live SSM validation exposed a presentation mismatch. SSM legitimately
deserved operator attention as an extreme current mover, but the large yellow
"EXTREME MOVER · LOOK NOW" banner remained visually unqualified while the same
record's unified Opportunity State correctly classified price >2% above VWAP as
CHASE / WAIT.

GS495 does not suppress attention. It aligns the extraordinary-event banner with
Walter's already-established GS310 anti-chase geometry:
* >2% above VWAP: LOOK NOW remains, but the label explicitly says
  EXTENDED / WATCH RESET and the guidance says attention only / do not chase.
* <=2% above VWAP: ordinary EXTREME MOVER · LOOK NOW wording remains.
* halts retain HALTED · WATCH RESUME priority.
* the existing >5% extreme branch remains semantically covered by the stricter
  >2% anti-chase presentation rule; no threshold used by trading logic changes.

Presentation only. No discovery, market data, indicators, scores, ranking, gates,
qualification, readiness, audio authority, execution, or orders change.
"""
from __future__ import annotations

from copy import deepcopy
from functools import wraps

ANTI_CHASE_VWAP_DISTANCE_PCT = 2.0
_OWNER = "_walter_gs495_extreme_attention_anti_chase_semantics"


def truthful_extreme_market_event(original, record: dict) -> dict | None:
    event = original(record)
    if not isinstance(event, dict):
        return event
    if event.get("halted"):
        return event

    try:
        distance = float(event.get("vwap_distance_pct"))
    except (TypeError, ValueError):
        distance = None

    if distance is None or distance <= ANTI_CHASE_VWAP_DISTANCE_PCT:
        return event

    view = deepcopy(event)
    view["label"] = "EXTREME MOVER · LOOK NOW · EXTENDED / WATCH RESET"
    view["guidance"] = (
        "Urgent attention only. Price is outside Walter's <=2% VWAP working zone; "
        "do not chase. Keep the chart visible and wait for a constructive reset "
        "toward VWAP before reconsidering."
    )
    view["anti_chase_active"] = True
    view["entry_authority_changed"] = False
    return view


def install() -> None:
    """Patch only GS333's event-description function at the late UI boundary."""
    from . import gs333_extreme_mover_operator_priority as gs333

    current = gs333.extreme_market_event
    if getattr(current, _OWNER, False):
        return

    @wraps(current)
    def extreme_market_event(record: dict) -> dict | None:
        return truthful_extreme_market_event(current, record)

    extreme_market_event._gs495_extreme_attention_anti_chase_semantics = True
    extreme_market_event._gs495_original = current
    setattr(extreme_market_event, _OWNER, True)
    gs333.extreme_market_event = extreme_market_event

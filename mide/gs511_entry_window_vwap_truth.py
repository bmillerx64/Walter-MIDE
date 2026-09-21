"""GS511: keep Entry Window truth inside Walter's established near-VWAP zone.

Sept. 21 pre-market validation exposed a presentation/audio contradiction:
NCPL was 4.2%-5.3% above VWAP and Walter's unified Opportunity State correctly said
CHASE / WAIT, yet the legacy escalation path briefly emitted ENTRY WINDOW OPEN because
candidate_status was still "Entry Ready".

That can also trigger the highest-urgency feed/audio semantics even though Walter's
existing readiness checklist requires price above and within 2% of VWAP.

GS511 changes only escalation/presentation truth:
- ENTRY WINDOW OPEN requires the existing near-VWAP condition (above and <=2%);
- >5% remains the existing TOO EXTENDED hard stop;
- an otherwise entry-ready record between +2% and +5% becomes WATCH CLOSELY rather
  than an entry window;
- below-VWAP records cannot become Entry Window Open;
- the live opportunity feed is rebound to the corrected snapshot on warm deploys.

No scanner score, qualification flag, ranking, participation, VWAP formula, ST truth,
execution or order behavior changes.
"""
from __future__ import annotations

from functools import wraps


_OWNER = "_walter_gs511_entry_window_vwap_truth"
NEAR_VWAP_MAX_PCT = 2.0


def _number(record: dict, key: str) -> float | None:
    value = record.get(key)
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _near_vwap(record: dict) -> bool:
    relation = str(record.get("vwap_relation") or "").strip().lower()
    distance = _number(record, "vwap_distance_pct")
    return relation == "above" and (
        distance is None or distance <= NEAR_VWAP_MAX_PCT
    )


def install() -> None:
    from . import escalation
    from . import live_opportunity_feed

    current_state = escalation.escalation_state
    if getattr(current_state, _OWNER, False):
        # Warm app.py reruns can retain live_opportunity_feed's imported function
        # binding even when escalation already owns GS511.
        live_opportunity_feed.escalation_snapshot = escalation.escalation_snapshot
        return

    current_snapshot = escalation.escalation_snapshot

    @wraps(current_state)
    def escalation_state(record: dict) -> str:
        existing = current_state(record)
        if existing != escalation.ENTRY_WINDOW_OPEN:
            return existing
        if _near_vwap(record):
            return existing

        # Preserve the legacy >5% hard stop if a retained wrapper ever hands us an
        # Entry Window state despite the base hard-stop ordering.
        distance = _number(record, "vwap_distance_pct")
        if distance is not None and distance > 5.0:
            return escalation.TOO_EXTENDED

        relation = str(record.get("vwap_relation") or "").strip().lower()
        trend = bool(
            record.get("supertrend_bullish") or record.get("supertrend_flip")
        )
        if relation == "above" and trend:
            return escalation.WATCH_CLOSELY
        return escalation.MONITOR

    @wraps(current_snapshot)
    def escalation_snapshot(record: dict) -> dict:
        snapshot = dict(current_snapshot(record))
        snapshot["state"] = escalation_state(record)
        return snapshot

    setattr(escalation_state, _OWNER, True)
    setattr(escalation_snapshot, _OWNER, True)
    escalation_state._gs511_original = current_state
    escalation_snapshot._gs511_original = current_snapshot

    escalation.escalation_state = escalation_state
    escalation.escalation_snapshot = escalation_snapshot

    # live_opportunity_feed imported escalation_snapshot by value. Rebind it so
    # feed entry_open truth follows the same corrected state in warm sessions.
    live_opportunity_feed.escalation_snapshot = escalation_snapshot

"""Presentation-only change detection for Walter's live opportunity feed."""

from __future__ import annotations

from datetime import datetime

from mide.escalation import escalation_snapshot
from mide.time_service import eastern_time

PARTICIPATION_THRESHOLD = 90.0
EXTENDED_DISTANCE = 2.0
# GS440: confidence is supporting evidence, not an operator action. Small scan-to-scan
# moves (+/-5 to +/-13 in live validation) were crowding out structural transitions.
MATERIAL_CONFIDENCE_DELTA = 15
FEED_EVENT_LIMIT = 10
FEED_TIME_BASIS = "America/New_York"
# GS440 bumps the presentation-history schema so warm Streamlit sessions immediately
# shed pre-refinement confidence chatter instead of carrying it for ten more rows.
FEED_SCHEMA_VERSION = 3


_EVENT_PRIORITY = {
    "ENTRY WINDOW OPEN": 100,
    "Entry Window closed": 95,
    "Lost VWAP": 90,
    "Too extended": 90,
    "VWAP reclaimed": 85,
    "SuperTrend flipped bullish": 85,
    "Pullback": 80,
    "Entered BUILDING": 70,
    "Entered MONITOR": 60,
    "Symbol removed from Focus": 30,
}


def _number(record: dict, *keys: str) -> float:
    for key in keys:
        value = record.get(key)
        if value is not None:
            try:
                return float(value)
            except (TypeError, ValueError):
                pass
    return 0.0


def opportunity_feed_snapshot(records: list[dict]) -> dict[str, dict]:
    """Capture only display evidence needed to compare priority symbols."""
    snapshots = {}
    for record in records:
        symbol = str(record.get("symbol") or "").upper()
        if not symbol:
            continue
        confidence = round(_number(record, "conviction_v2_score", "conviction_score"))
        candidate_state = str(
            record.get("candidate_status") or record.get("status") or ""
        ).strip()
        distance = _number(record, "vwap_distance_pct")
        snapshots[symbol] = {
            "participation": _number(
                record, "participation_surge_score", "participation_score"
            ),
            "vwap": str(record.get("vwap_relation") or "below").lower(),
            "supertrend": bool(record.get("supertrend_bullish")),
            "confidence": confidence,
            "entry_open": escalation_snapshot(record)["state"] == "Entry Window Open",
            "extended": distance > EXTENDED_DISTANCE,
            "building": candidate_state in {"Strengthening", "ALERT", "WATCH NOW"}
            or (candidate_state in {"Watching", "MONITOR"} and confidence >= 75),
            "monitor": candidate_state in {"Watching", "MONITOR", "Emerging", "New"},
            "pullback": str(record.get("vwap_relation") or "").lower() == "testing",
        }
    return snapshots


def _event(symbol: str, message: str, color: str, when: datetime, delta=None) -> dict:
    """Build one feed event using Walter's user-facing U.S. market clock."""
    return {
        "time": eastern_time(when).strftime("%H:%M:%S"),
        "time_basis": FEED_TIME_BASIS,
        "schema_version": FEED_SCHEMA_VERSION,
        "symbol": symbol,
        "message": message,
        "color": color,
        "confidence_delta": delta,
    }


def _is_current_clock_event(event: dict) -> bool:
    """Reject feed rows created before the current explicit ET/history schema."""
    return (
        event.get("time_basis") == FEED_TIME_BASIS
        and event.get("schema_version") == FEED_SCHEMA_VERSION
    )


def _event_priority(event: dict) -> tuple[int, int]:
    """Rank same-scan feed changes by what should move the trader's eyes first."""
    message = str(event.get("message") or "")
    if message.startswith("Participation "):
        priority = 75
    elif message.startswith("Confidence "):
        priority = 40
    else:
        priority = _EVENT_PRIORITY.get(message, 50)
    delta = abs(int(event.get("confidence_delta") or 0))
    return priority, delta


def opportunity_feed_changes(
    previous: dict[str, dict], current: dict[str, dict], when: datetime
) -> list[dict]:
    """Describe material state transitions without affecting scanner decisions.

    GS440 keeps confidence as a supporting-only feed cue. A standalone confidence move
    must be large enough to matter, and it is omitted when the same symbol already has
    a structural/action transition in that scan. That mirrors the operator workflow:
    show *what changed in the trade*, not every intermediate score wobble.
    """
    events = []
    for symbol, state in current.items():
        prior = previous.get(symbol)
        if prior is None:
            continue

        symbol_events = []
        if prior["participation"] < PARTICIPATION_THRESHOLD <= state["participation"]:
            symbol_events.append(
                _event(
                    symbol,
                    f"Participation {round(prior['participation'])}→{round(state['participation'])}",
                    "green",
                    when,
                )
            )
        if prior["vwap"] != "above" and state["vwap"] == "above":
            symbol_events.append(_event(symbol, "VWAP reclaimed", "green", when))
        elif prior["vwap"] in {"above", "testing"} and state["vwap"] == "below":
            symbol_events.append(_event(symbol, "Lost VWAP", "red", when))
        if not prior["supertrend"] and state["supertrend"]:
            symbol_events.append(
                _event(symbol, "SuperTrend flipped bullish", "green", when)
            )
        if not prior["entry_open"] and state["entry_open"]:
            symbol_events.append(_event(symbol, "ENTRY WINDOW OPEN", "green", when))
        elif prior["entry_open"] and not state["entry_open"]:
            symbol_events.append(_event(symbol, "Entry Window closed", "red", when))

        pullback_emitted = False
        if not prior.get("extended") and state["extended"]:
            symbol_events.append(_event(symbol, "Too extended", "red", when))
        elif prior.get("extended") and not state["extended"]:
            symbol_events.append(_event(symbol, "Pullback", "yellow", when))
            pullback_emitted = True
        if (
            not prior.get("building")
            and state.get("building")
            and not state["entry_open"]
        ):
            symbol_events.append(_event(symbol, "Entered BUILDING", "yellow", when))
        elif (
            not prior.get("monitor")
            and state.get("monitor")
            and not state.get("building")
        ):
            symbol_events.append(_event(symbol, "Entered MONITOR", "yellow", when))
        if (
            not pullback_emitted
            and not prior.get("pullback")
            and state.get("pullback")
            and not state["extended"]
        ):
            symbol_events.append(_event(symbol, "Pullback", "yellow", when))

        confidence_delta = state["confidence"] - prior["confidence"]
        if (
            not symbol_events
            and abs(confidence_delta) >= MATERIAL_CONFIDENCE_DELTA
        ):
            symbol_events.append(
                _event(
                    symbol,
                    f"Confidence {confidence_delta:+d}",
                    "green" if confidence_delta > 0 else "red",
                    when,
                    confidence_delta,
                )
            )

        events.extend(symbol_events)

    for symbol in previous.keys() - current.keys():
        events.append(_event(symbol, "Symbol removed from Focus", "red", when))
    return events


def update_opportunity_feed(
    records: list[dict], previous: dict[str, dict], events: list[dict], when: datetime
) -> tuple[dict[str, dict], list[dict]]:
    """Return the new snapshot and a newest-first, ten-event operator log.

    GS440 orders changes from the same scan by operator consequence rather than code
    generation order: entry-window changes first, then risk/structure, then setup
    development, then rare standalone confidence moves and Focus housekeeping.
    Historical rows from older presentation schemas are dropped intentionally; they
    are UI history only and should not survive a live signal-to-noise refinement.
    """
    current = opportunity_feed_snapshot(records)
    changes = opportunity_feed_changes(previous, current, when) if previous else []
    prioritized_changes = sorted(changes, key=_event_priority, reverse=True)
    retained = [event for event in events if _is_current_clock_event(event)]
    return current, (prioritized_changes + retained)[:FEED_EVENT_LIMIT]

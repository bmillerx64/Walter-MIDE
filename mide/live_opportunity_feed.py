"""Presentation-only change detection for Walter's live opportunity feed."""

from __future__ import annotations

from datetime import datetime

from mide.escalation import escalation_snapshot

PARTICIPATION_THRESHOLD = 90.0
EXTENDED_DISTANCE = 2.0
MATERIAL_CONFIDENCE_DELTA = 5
FEED_EVENT_LIMIT = 10


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
    return {
        "time": when.strftime("%H:%M:%S"),
        "symbol": symbol,
        "message": message,
        "color": color,
        "confidence_delta": delta,
    }


def opportunity_feed_changes(
    previous: dict[str, dict], current: dict[str, dict], when: datetime
) -> list[dict]:
    """Describe material state transitions without affecting scanner decisions."""
    events = []
    for symbol, state in current.items():
        prior = previous.get(symbol)
        if prior is None:
            continue
        if prior["participation"] < PARTICIPATION_THRESHOLD <= state["participation"]:
            events.append(
                _event(
                    symbol,
                    f"Participation {round(prior['participation'])}→{round(state['participation'])}",
                    "green",
                    when,
                )
            )
        if prior["vwap"] != "above" and state["vwap"] == "above":
            events.append(_event(symbol, "VWAP reclaimed", "green", when))
        elif prior["vwap"] in {"above", "testing"} and state["vwap"] == "below":
            events.append(_event(symbol, "Lost VWAP", "red", when))
        if not prior["supertrend"] and state["supertrend"]:
            events.append(_event(symbol, "SuperTrend flipped bullish", "green", when))
        confidence_delta = state["confidence"] - prior["confidence"]
        if abs(confidence_delta) >= MATERIAL_CONFIDENCE_DELTA:
            events.append(
                _event(
                    symbol,
                    f"Confidence {confidence_delta:+d}",
                    "green" if confidence_delta > 0 else "red",
                    when,
                    confidence_delta,
                )
            )
        if not prior["entry_open"] and state["entry_open"]:
            events.append(_event(symbol, "ENTRY WINDOW OPEN", "green", when))
        elif prior["entry_open"] and not state["entry_open"]:
            events.append(_event(symbol, "Entry Window closed", "red", when))
        pullback_emitted = False
        if not prior.get("extended") and state["extended"]:
            events.append(_event(symbol, "Too extended", "red", when))
        elif prior.get("extended") and not state["extended"]:
            events.append(_event(symbol, "Pullback", "yellow", when))
            pullback_emitted = True
        if (
            not prior.get("building")
            and state.get("building")
            and not state["entry_open"]
        ):
            events.append(_event(symbol, "Entered BUILDING", "yellow", when))
        elif (
            not prior.get("monitor")
            and state.get("monitor")
            and not state.get("building")
        ):
            events.append(_event(symbol, "Entered MONITOR", "yellow", when))
        if (
            not pullback_emitted
            and not prior.get("pullback")
            and state.get("pullback")
            and not state["extended"]
        ):
            events.append(_event(symbol, "Pullback", "yellow", when))

    for symbol in previous.keys() - current.keys():
        events.append(_event(symbol, "Symbol removed from Focus", "red", when))
    return events


def update_opportunity_feed(
    records: list[dict], previous: dict[str, dict], events: list[dict], when: datetime
) -> tuple[dict[str, dict], list[dict]]:
    """Return the new snapshot and a newest-first, ten-event mission log."""
    current = opportunity_feed_snapshot(records)
    changes = opportunity_feed_changes(previous, current, when) if previous else []
    return current, (list(reversed(changes)) + list(events))[:FEED_EVENT_LIMIT]

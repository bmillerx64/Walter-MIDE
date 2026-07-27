"""Presentation-only change detection for Walter's live opportunity feed."""

from __future__ import annotations

from datetime import datetime

from mide.escalation import escalation_snapshot

PARTICIPATION_THRESHOLD = 90.0
EXTENDED_DISTANCE = 2.0
MATERIAL_CONFIDENCE_DELTA = 5


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
        snapshots[symbol] = {
            "participation": _number(
                record, "participation_surge_score", "participation_score"
            ),
            "vwap": str(record.get("vwap_relation") or "below").lower(),
            "supertrend": bool(record.get("supertrend_bullish")),
            "confidence": round(
                _number(record, "conviction_v2_score", "conviction_score")
            ),
            "entry_open": escalation_snapshot(record)["state"]
            == "Entry Window Open",
            "extended": _number(record, "vwap_distance_pct")
            > EXTENDED_DISTANCE,
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
                _event(symbol, "Participation crossed 90", "green", when)
            )
        if prior["vwap"] != "above" and state["vwap"] == "above":
            events.append(_event(symbol, "VWAP reclaimed", "green", when))
        elif prior["vwap"] in {"above", "testing"} and state["vwap"] == "below":
            events.append(_event(symbol, "Lost VWAP", "red", when))
        if not prior["supertrend"] and state["supertrend"]:
            events.append(
                _event(symbol, "SuperTrend flipped bullish", "green", when)
            )
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
            events.append(_event(symbol, "Entry Window opened", "green", when))
        elif prior["entry_open"] and not state["entry_open"]:
            events.append(_event(symbol, "Entry Window closed", "red", when))
        if not prior["extended"] and state["extended"]:
            events.append(_event(symbol, "Candidate became extended", "yellow", when))

    for symbol in previous.keys() - current.keys():
        events.append(_event(symbol, "Symbol removed from Focus", "red", when))
    return events


def update_opportunity_feed(
    records: list[dict], previous: dict[str, dict], events: list[dict], when: datetime
) -> tuple[dict[str, dict], list[dict]]:
    """Return the new snapshot and a newest-first, twenty-event mission log."""
    current = opportunity_feed_snapshot(records)
    changes = opportunity_feed_changes(previous, current, when) if previous else []
    return current, (list(reversed(changes)) + list(events))[:20]

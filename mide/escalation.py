"""Walter 2.12 display-only recommendation intelligence.

The engine intentionally consumes completed scanner records and never mutates
them. Scanner qualification, ranking, thresholds, and scores remain the source
of truth; this module only explains how urgently a trader should review them.
"""

from __future__ import annotations

from dataclasses import dataclass

from mide.timeframe_alignment import alignment_voice

ENTRY_WINDOW_OPEN = "Entry Window Open"
WATCH_CLOSELY = "Watch Closely"
MONITOR = "Monitor"
TOO_EXTENDED = "Too Extended"

GREEN_LIGHT = "GREEN LIGHT"
GET_READY = "GET READY"
NO_TRADE = "NO TRADE"


def _number(record: dict, *keys: str) -> float | None:
    for key in keys:
        value = record.get(key)
        if value is not None:
            try:
                return float(value)
            except (TypeError, ValueError):
                continue
    return None


def ready_checklist(record: dict) -> list[dict]:
    """Expose existing scanner evidence as a consistent readiness checklist."""
    relation = str(record.get("vwap_relation") or "").lower()
    distance = _number(record, "vwap_distance_pct")
    participation_gate = record.get("participation_gate") or {}
    structure_gate = record.get("structure_gate") or {}
    trigger = record.get("trigger_diagnostics") or {}
    return [
        {
            "label": "Participation qualified",
            "ready": participation_gate.get(
                "passed", record.get("qualified_for_watch", True)
            )
            is not False,
        },
        {
            "label": "Structure qualified",
            "ready": structure_gate.get("passed", True) is not False,
        },
        {
            "label": "Holding above VWAP",
            "ready": relation == "above" and (distance is None or distance <= 2.0),
        },
        {
            "label": "Trend confirmation",
            "ready": bool(
                record.get("supertrend_bullish") or record.get("supertrend_flip")
            ),
        },
        {
            "label": "Entry trigger",
            "ready": trigger.get("passed", record.get("qualified_for_entry", False))
            is True,
        },
    ]


def trade_recommendation(record: dict) -> dict:
    """Give one unambiguous preparation recommendation from existing evidence."""
    checklist = ready_checklist(record)
    remaining = [item for item in checklist if not item["ready"]]
    distance = _number(record, "vwap_distance_pct")
    if distance is not None and distance > 5.0:
        return {
            "label": NO_TRADE,
            "emoji": "🔴",
            "message": "This setup is too extended. Do not prepare an entry.",
            "remaining": len(remaining),
        }
    if not remaining:
        return {
            "label": GREEN_LIGHT,
            "emoji": "🟢",
            "message": "Everything Walter requires has aligned. Watch the next candle for entry.",
            "remaining": 0,
        }
    if len(remaining) == 1:
        return {
            "label": GET_READY,
            "emoji": "🟡",
            "message": f"One condition remains: {remaining[0]['label']}.",
            "remaining": 1,
        }
    return {
        "label": NO_TRADE,
        "emoji": "🔴",
        "message": f"{len(remaining)} required conditions are not aligned.",
        "remaining": len(remaining),
    }


def confidence_trend(record: dict) -> dict:
    """Describe confidence direction from already-computed conviction evidence."""
    current = _number(
        record,
        "conviction_v2_score",
        "conviction_score",
        "scanner_v2_score",
        "opportunity_score",
    )
    prior = record.get("opportunity_pulse_previous") or {}
    previous = _number(
        prior,
        "conviction_v2_score",
        "conviction_score",
        "scanner_v2_score",
        "opportunity_score",
    )
    delta = _number(record, "conviction_delta")
    if delta is None and current is not None and previous is not None:
        delta = current - previous
    delta = delta or 0.0
    direction = "Rising" if delta > 1 else "Falling" if delta < -1 else "Steady"
    return {"direction": direction, "delta": round(delta, 1), "current": current}


@dataclass(frozen=True)
class EvidenceMetric:
    label: str
    keys: tuple[str, ...]
    meaningful_change: float
    suffix: str = ""


EVIDENCE_METRICS = (
    EvidenceMetric(
        "Confidence", ("conviction_v2_score", "conviction_score"), 2.0, " pts"
    ),
    EvidenceMetric(
        "Participation",
        ("participation_surge_score", "participation_score"),
        3.0,
        " pts",
    ),
    EvidenceMetric("Expansion quality", ("expansion_quality",), 3.0, " pts"),
    EvidenceMetric("VWAP distance", ("vwap_distance_pct",), 0.25, "%"),
    EvidenceMetric("Volume acceleration", ("volume_acceleration",), 0.15, "×"),
    EvidenceMetric("RVOL", ("rvol_proxy", "rvol"), 0.25, "×"),
)


def meaningful_evidence_deltas(record: dict) -> list[dict]:
    """Return only material numeric changes from the immediately prior scan."""
    previous = record.get("opportunity_pulse_previous") or {}
    deltas = []
    for metric in EVIDENCE_METRICS:
        current = _number(record, *metric.keys)
        prior = _number(previous, *metric.keys)
        if current is None or prior is None:
            continue
        delta = current - prior
        if abs(delta) < metric.meaningful_change:
            continue
        improving = delta < 0 if metric.label == "VWAP distance" else delta > 0
        deltas.append(
            {
                "label": metric.label,
                "delta": round(delta, 2),
                "display": f"{delta:+.1f}{metric.suffix}",
                "direction": "improved" if improving else "weakened",
            }
        )
    return deltas


def momentum_urgency(record: dict) -> dict:
    """Detect multi-signal improvement without changing scanner decisions.

    GS293 deliberately requires a fresh prior observation. A symbol is promoted
    for review only when structure/trend remain supportive and the newest scan
    shows additional improvement. This prevents a single hot print, stale record,
    or raw price jump from manufacturing urgency.
    """
    previous = record.get("opportunity_pulse_previous") or {}
    continuity = bool(previous) or int(record.get("consecutive_reevaluations") or 0) >= 2
    relation = str(record.get("vwap_relation") or "").lower()
    distance = _number(record, "vwap_distance_pct")
    vwap_supported = relation == "above" and (distance is None or distance <= 2.0)
    trend_supported = bool(record.get("supertrend_bullish") or record.get("supertrend_flip"))
    confidence = confidence_trend(record)
    deltas = meaningful_evidence_deltas(record)
    improving = [item for item in deltas if item["direction"] == "improved"]
    weakening = [item for item in deltas if item["direction"] == "weakened"]

    promoted = bool(
        continuity
        and vwap_supported
        and trend_supported
        and confidence["direction"] == "Rising"
        and len(improving) >= 2
        and len(weakening) <= 1
    )
    return {
        "promoted": promoted,
        "continuity": continuity,
        "vwap_supported": vwap_supported,
        "trend_supported": trend_supported,
        "confidence_direction": confidence["direction"],
        "improving_signals": [item["label"] for item in improving],
        "weakening_signals": [item["label"] for item in weakening],
    }


def escalation_state(record: dict) -> str:
    """Translate existing decisions plus fresh momentum evidence into urgency."""
    distance = _number(record, "vwap_distance_pct")
    if distance is not None and distance > 5.0:
        return TOO_EXTENDED
    state = record.get("candidate_status") or record.get("status")
    if record.get("qualified_for_entry") is True or state in {
        "Entry Ready",
        "EXCEPTIONAL",
    }:
        return ENTRY_WINDOW_OPEN
    if state in {"Strengthening", "ALERT", "WATCH NOW"}:
        return WATCH_CLOSELY
    if momentum_urgency(record)["promoted"]:
        return WATCH_CLOSELY
    return MONITOR


def escalation_snapshot(record: dict) -> dict:
    return {
        "symbol": str(record.get("symbol") or "").upper(),
        "state": escalation_state(record),
        "confidence_trend": confidence_trend(record),
        "urgency": momentum_urgency(record),
        "checklist": ready_checklist(record),
        "recommendation": trade_recommendation(record),
        "deltas": meaningful_evidence_deltas(record),
    }


def escalation_state_changes(records: list[dict]) -> list[dict]:
    """Find actual escalation transitions using each record's prior scan."""
    changes = []
    for record in records:
        previous = record.get("opportunity_pulse_previous") or {}
        if not previous:
            continue
        old, new = escalation_state(previous), escalation_state(record)
        if old != new:
            changes.append(
                {
                    "symbol": str(record.get("symbol") or "").upper(),
                    "from": old,
                    "to": new,
                }
            )
    return changes


def escalation_alert_phrase(records: list[dict]) -> str:
    changes = escalation_state_changes(records)
    if not changes:
        return ""
    first = changes[0]
    phrase = f"{first['symbol']} escalation changed to {first['to']}."
    record = next(
        (r for r in records if str(r.get("symbol") or "").upper() == first["symbol"]),
        {},
    )
    alignment = alignment_voice(record)
    if alignment:
        phrase += f" {alignment}"
    if len(changes) > 1:
        phrase += f" {len(changes) - 1} additional state change{'s' if len(changes) > 2 else ''}."
    return phrase

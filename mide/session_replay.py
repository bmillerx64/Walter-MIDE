"""Read-only reconstruction of a symbol's runtime session.

The replay deliberately consumes Candidate History and Flight Recorder exports;
it does not participate in scanning, qualification, scoring, or alerts.
"""

from __future__ import annotations

from collections import Counter
from typing import Any


def _stamp(item: dict) -> str:
    return str(item.get("scan_timestamp") or item.get("timestamp") or "")


def _state(item: dict) -> str:
    return str(
        item.get("candidate_status")
        or item.get("workflow_state")
        or item.get("status")
        or "Candidate"
    )


def _number(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _recommendation(record: dict) -> str:
    return str(
        record.get("recommendation")
        or record.get("tradeability")
        or record.get("action")
        or ("Entry Ready" if record.get("qualified_for_entry") else "Wait")
    )


def _blocker_category(text: str, condition: str = "") -> str:
    """Give a retained diagnostic a presentation label without re-evaluating it."""
    value = f"{condition} {text}".lower()
    if any(
        word in value for word in ("participation", "volume", "dollar flow", "buying")
    ):
        return "Participation"
    if "expansion" in value:
        return "Expansion"
    if "vwap" in value or "extension" in value:
        return "VWAP"
    if "supertrend" in value or "trend" in value:
        return "SuperTrend"
    if "trigger" in value:
        return "Trigger"
    return "Other"


def _promotion_blockers(record: dict) -> list[dict]:
    """Expose only failed checks retained for this scan, with measured evidence."""
    details: list[dict] = []

    def add(
        reason: Any,
        condition: Any = None,
        measured: Any = None,
        threshold: Any = None,
        category: str | None = None,
    ):
        if not reason:
            return
        text = str(reason)
        item = {
            "category": category or _blocker_category(text, str(condition or "")),
            "reason": text,
        }
        if condition:
            item["condition"] = str(condition)
        if measured is not None:
            item["measured"] = measured
        if threshold is not None:
            item["threshold"] = threshold
        identity = (item["category"], item["reason"], item.get("condition"))
        if identity not in {
            (existing["category"], existing["reason"], existing.get("condition"))
            for existing in details
        }:
            details.append(item)

    for gate_name, category in (
        ("participation_gate", "Participation"),
        ("structure_gate", None),
    ):
        gate = record.get(gate_name) or {}
        for check in gate.get("checks") or gate.get("failed_criteria") or []:
            if check.get("passed") is False or "passed" not in check:
                add(
                    check.get("failed_reason") or check.get("condition"),
                    check.get("condition"),
                    check.get("measured"),
                    check.get("threshold"),
                    category,
                )
        # Older exports retained reasons but not individual checks.
        if not gate.get("checks") and not gate.get("failed_criteria"):
            for reason in gate.get("failed_reasons") or []:
                add(reason, category=category)

    trigger = record.get("trigger_diagnostics") or {}
    for check in trigger.get("checks") or []:
        if not check.get("passed"):
            add(
                check.get("failed_reason") or check.get("condition"),
                check.get("condition"),
                check.get("measured"),
                check.get("threshold"),
                None,
            )
    for reason in record.get("trigger_failed_conditions") or []:
        add(reason)
    if trigger.get("passed") is False and not trigger.get("checks"):
        add("Trigger did not pass", category="Trigger")
    for reason in record.get("entry_blockers_explained") or []:
        add(reason)
    if not details and record.get("latest_rejection_or_blocker"):
        add(record["latest_rejection_or_blocker"])
    return details


def _compress_scans(scans: list[dict]) -> list[dict]:
    """Collapse adjacent scans with the same visible state and exact blockers."""
    events: list[dict] = []
    for scan in scans:
        signature = (
            scan["state"],
            scan["recommendation"],
            scan.get("quality_score"),
            scan.get("quality_grade"),
            scan.get("relative_strength_score"),
            tuple(
                (item["category"], item["reason"])
                for item in scan["promotion_blockers"]
            ),
        )
        if events and events[-1]["_signature"] == signature:
            events[-1]["end_timestamp"] = scan["timestamp"]
            events[-1]["scan_count"] += 1
            events[-1]["scan_ids"].append(scan.get("scan_id"))
            continue
        event = dict(scan)
        event.update(
            {
                "end_timestamp": scan["timestamp"],
                "scan_count": 1,
                "scan_ids": [scan.get("scan_id")],
                "_signature": signature,
            }
        )
        events.append(event)
    for event in events:
        event.pop("_signature")
    return events


def _readiness(record: dict) -> tuple:
    state_rank = {
        "Entry Ready": 5,
        "Strengthening": 4,
        "Watching": 3,
        "Watch List": 3,
        "Emerging": 2,
    }.get(_state(record), 1)
    return (
        state_rank,
        int(bool(record.get("qualified_for_entry"))),
        int(bool(record.get("trigger_result") or record.get("trigger"))),
        _number(record.get("opportunity_score")),
        _number(record.get("conviction_v2_score", record.get("conviction_score"))),
    )


def build_session_replay(bundle: dict) -> dict:
    """Build a chronological, presentation-only replay from an export bundle."""
    symbol = str(bundle.get("symbol") or "").strip().upper()
    candidates = sorted(bundle.get("candidate_history") or [], key=_stamp)
    candidate_by_stamp = {_stamp(item): item for item in candidates if _stamp(item)}
    scans = []
    for trace in sorted(bundle.get("flight_recorder") or [], key=_stamp):
        evidence = dict(trace.get("evidence") or {})
        candidate = candidate_by_stamp.get(_stamp(trace), {})
        record = {**evidence, **candidate}
        record.update(
            {
                "timestamp": _stamp(trace),
                "scan_id": trace.get("scan_id"),
                "stage_reached": trace.get("stage_reached"),
                "state": _state(record),
                "quality_score": record.get("quality_score"),
                "quality_grade": record.get("quality_grade"),
                "participation_surge": record.get(
                    "participation_surge_detected",
                    record.get("participation_surge_score"),
                ),
                "expansion_quality": record.get("expansion_quality"),
                "vwap_distance": record.get(
                    "vwap_distance_pct", record.get("vwap_distance")
                ),
                "supertrend_state": record.get("supertrend_state")
                or (
                    "bullish"
                    if record.get("supertrend_bullish")
                    else (
                        "bearish" if record.get("supertrend_bullish") is False else None
                    )
                ),
                "alignment_score": record.get("alignment_score"),
                "alignment_total": record.get("alignment_total", 3),
                "alignment_label": record.get("alignment_label"),
                "timeframe_alignment": record.get("timeframe_alignment") or {},
                "vpi": record.get("volume_pace_ratio", record.get("vpi")),
                "volume_acceleration": record.get(
                    "acceleration_ratio",
                    record.get(
                        "five_minute_vpi_acceleration",
                        record.get("legacy_volume_acceleration"),
                    ),
                ),
                "relative_strength_score": record.get("relative_strength_score"),
                "relative_strength_benchmark": record.get(
                    "relative_strength_benchmark"
                ),
                "recommendation": _recommendation(record),
                "trigger_diagnostics": record.get("trigger_diagnostics") or {},
                "promotion_blockers": _promotion_blockers(record),
            }
        )
        record["blockers"] = [item["reason"] for item in record["promotion_blockers"]]
        scans.append(record)

    # Candidate History may retain a ranked record when an older recorder did not.
    known = {item["timestamp"] for item in scans}
    for candidate in candidates:
        if _stamp(candidate) not in known:
            record = dict(candidate)
            record.update(
                {
                    "timestamp": _stamp(candidate),
                    "scan_id": candidate.get("scan_id"),
                    "stage_reached": None,
                    "state": _state(candidate),
                    "quality_score": candidate.get("quality_score"),
                    "quality_grade": candidate.get("quality_grade"),
                    "participation_surge": candidate.get(
                        "participation_surge_detected",
                        candidate.get("participation_surge_score"),
                    ),
                    "vwap_distance": candidate.get("vwap_distance_pct"),
                    "supertrend_state": candidate.get("supertrend_state")
                    or (
                        "bullish"
                        if candidate.get("supertrend_bullish")
                        else (
                            "bearish"
                            if candidate.get("supertrend_bullish") is False
                            else None
                        )
                    ),
                    "vpi": candidate.get("volume_pace_ratio"),
                    "volume_acceleration": candidate.get(
                        "acceleration_ratio", candidate.get("volume_acceleration")
                    ),
                    "relative_strength_score": candidate.get(
                        "relative_strength_score"
                    ),
                    "relative_strength_benchmark": candidate.get(
                        "relative_strength_benchmark"
                    ),
                    "recommendation": _recommendation(candidate),
                    "promotion_blockers": _promotion_blockers(candidate),
                }
            )
            record["blockers"] = [
                item["reason"] for item in record["promotion_blockers"]
            ]
            scans.append(record)
    scans.sort(key=lambda item: item["timestamp"])

    def first(predicate):
        return next((item["timestamp"] for item in scans if predicate(item)), None)

    closest = max(scans, key=_readiness) if scans else None
    milestones = {
        "First discovered": scans[0]["timestamp"] if scans else None,
        "First Candidate": first(
            lambda item: item["state"]
            not in {"Removed", "PASS", "Rejected – No Participation"}
        ),
        "First Watch List": first(
            lambda item: item["state"] in {"Watching", "Watch List"}
        ),
        "First Strengthening": first(lambda item: item["state"] == "Strengthening"),
        "Closest Entry Ready moment": closest["timestamp"] if closest else None,
        "Removal from tracking": first(
            lambda item: item["state"] in {"Removed", "PASS"}
        ),
    }
    blocker_counts = Counter(
        (blocker["category"], blocker["reason"])
        for item in scans
        for blocker in item["promotion_blockers"]
    )
    limiting_pair, limiting_count = (
        blocker_counts.most_common(1)[0] if blocker_counts else ((None, None), 0)
    )
    limiting = f"{limiting_pair[0]} — {limiting_pair[1]}" if limiting_pair[0] else None
    promoted = [
        item
        for item in scans
        if item["state"] in {"Watching", "Watch List", "Strengthening", "Entry Ready"}
    ]
    peak = closest or {}
    promotion_signals = []
    if (
        _number(peak.get("participation_surge_score")) >= 60
        or peak.get("participation_surge") is True
    ):
        promotion_signals.append("participation surged")
    if _number(peak.get("expansion_quality")) >= 55:
        promotion_signals.append("expansion quality was constructive")
    if str(peak.get("supertrend_state", "")).lower() == "bullish":
        promotion_signals.append("SuperTrend was bullish")
    why_promoted = (
        "Walter promoted the stock because " + ", ".join(promotion_signals) + "."
        if promoted and promotion_signals
        else (
            "Walter retained or promoted the stock as its recorded workflow qualifications improved."
            if promoted
            else "Walter did not promote the stock beyond discovery in the retained session."
        )
    )
    entered = any(
        item["state"] == "Entry Ready" or item.get("qualified_for_entry")
        for item in scans
    )
    why_no_entry = (
        "Walter recorded an Entry Ready qualification during this session."
        if entered
        else (
            f"Walter did not recommend entry because {limiting}."
            if limiting
            else "Walter did not recommend entry because the retained scans never confirmed all entry rules."
        )
    )
    events = _compress_scans(scans)
    return {
        "symbol": symbol,
        "milestones": milestones,
        "scans": events,
        "summary": {
            "why_promoted": why_promoted,
            "why_no_entry": why_no_entry,
            "most_limiting_rule": limiting or "None recorded",
            "most_limiting_rule_count": limiting_count,
            "total_scans": len(scans),
            "summarized_events": len(events),
        },
    }

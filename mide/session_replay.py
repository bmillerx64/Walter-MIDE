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


def _blockers(record: dict) -> list[str]:
    blockers = [
        str(value) for value in record.get("entry_blockers_explained") or [] if value
    ]
    trigger = record.get("trigger_diagnostics") or {}
    for check in trigger.get("checks") or []:
        if not check.get("passed"):
            reason = check.get("failed_reason") or check.get("condition")
            if reason:
                blockers.append(str(reason))
    blockers.extend(
        str(value) for value in record.get("trigger_failed_conditions") or [] if value
    )
    if not blockers and record.get("latest_rejection_or_blocker"):
        blockers.append(str(record["latest_rejection_or_blocker"]))
    return list(dict.fromkeys(blockers))


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
                "vpi": record.get("volume_pace_ratio", record.get("vpi")),
                "volume_acceleration": record.get(
                    "acceleration_ratio",
                    record.get(
                        "five_minute_vpi_acceleration",
                        record.get("legacy_volume_acceleration"),
                    ),
                ),
                "recommendation": _recommendation(record),
                "trigger_diagnostics": record.get("trigger_diagnostics") or {},
                "blockers": _blockers(record),
            }
        )
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
                    "recommendation": _recommendation(candidate),
                    "blockers": _blockers(candidate),
                }
            )
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
    blocker_counts = Counter(blocker for item in scans for blocker in item["blockers"])
    limiting = blocker_counts.most_common(1)[0][0] if blocker_counts else None
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
    return {
        "symbol": symbol,
        "milestones": milestones,
        "scans": scans,
        "summary": {
            "why_promoted": why_promoted,
            "why_no_entry": why_no_entry,
            "most_limiting_rule": limiting or "None recorded",
        },
    }

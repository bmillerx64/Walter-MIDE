from __future__ import annotations

from datetime import datetime
from numbers import Real

TRADER_PRIORITY_RANK = {
    "ORDINARY": 1,
    "ACTIVE": 2,
    "STRONG": 3,
    "ENTRY READY": 4,
    "ROCKET": 5,
}

_STATUS_PRIORITY_ALIASES = {
    "EXCEPTIONAL": "ROCKET",
    "ALERT": "ROCKET",
    "ENTRY READY": "ENTRY READY",
    "STRENGTHENING": "STRONG",
    "WATCH NOW": "STRONG",
    "WATCHING": "ACTIVE",
    "EMERGING": "ACTIVE",
    "MONITOR": "ACTIVE",
    "NEW": "ORDINARY",
    "WEAKENING": "ORDINARY",
    "REMOVED": "ORDINARY",
    "PASS": "ORDINARY",
}


def sortable_text(value) -> str:
    """Return a stable text value for sort keys that may contain mixed types."""
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def sortable_number(value) -> float:
    """Return a numeric sort value while treating missing/non-numeric values predictably."""
    if value is None or value == "":
        return 0.0
    if isinstance(value, Real):
        return float(value)
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def trader_priority_label(record: dict) -> str:
    """Return the trader-facing priority bucket for a scanner record."""
    for field in (
        "trader_priority",
        "priority",
        "status",
        "candidate_status",
        "participation_tier",
    ):
        value = record.get(field)
        if not value:
            continue
        normalized = str(value).strip().upper().replace("_", " ")
        if normalized in TRADER_PRIORITY_RANK:
            return normalized
        if normalized in _STATUS_PRIORITY_ALIASES:
            return _STATUS_PRIORITY_ALIASES[normalized]
    return "ORDINARY"


def trader_priority_sort_key(record: dict) -> tuple[float, float, str]:
    """Sort by current momentum first, then historical strength and recency."""
    if "current_momentum" in record or "historical_strength" in record:
        current = sortable_number(
            record.get(
                "current_momentum",
                record.get("scanner_v2_score", record.get("opportunity_score", 0)),
            )
        )
        historical = sortable_number(
            record.get(
                "historical_strength",
                record.get("attention_score", record.get("conviction_score", 0)),
            )
        )
        return (
            current,
            historical,
            sortable_text(record.get("state_entered_at") or record.get("timestamp")),
        )
    return (
        float(TRADER_PRIORITY_RANK[trader_priority_label(record)]),
        sortable_number(
            record.get("conviction_score", record.get("scanner_v2_score", 0))
        ),
        sortable_text(record.get("state_entered_at") or record.get("timestamp")),
    )

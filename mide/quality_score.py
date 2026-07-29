"""Presentation-only alert quality ranking from existing scanner signals."""

from __future__ import annotations

import math
from typing import Any

QUALITY_WEIGHTS = {
    "participation": 20.0,
    "structure": 20.0,
    "vwap_quality": 15.0,
    "trend_confirmation": 15.0,
    "relative_volume": 10.0,
    "volume_acceleration": 10.0,
    "extension_quality": 10.0,
}


def _number(record: dict, key: str, default: float = 0.0) -> float:
    try:
        return float(record.get(key, default) or 0.0)
    except (TypeError, ValueError):
        return default


def _bounded(value: float) -> float:
    return max(0.0, min(100.0, value))


def quality_grade(score: float) -> str:
    """Return the requested attention grade for a 0–100 quality score."""
    if score >= 95:
        return "A+"
    if score >= 90:
        return "A"
    if score >= 85:
        return "B+"
    if score >= 80:
        return "B"
    if score >= 75:
        return "C"
    return "Watch Only"


def calculate_quality_score(record: dict) -> dict:
    """Score existing evidence without affecting any scanner decision predicate."""
    participation = max(
        _number(record, "participation_score"),
        _number(record, "participation_surge_score"),
    )

    structure = (
        (40.0 if record.get("higher_lows") else 0.0)
        + (30.0 if record.get("near_hod") else 0.0)
        + (30.0 if record.get("ema65_relation") == "above" else 0.0)
        + (
            15.0
            if record.get("ema65_relation") != "above"
            and _number(record, "ema65_distance_pct", 99) <= 1.5
            else 0.0
        )
    )

    relation = record.get("vwap_relation")
    distance = abs(_number(record, "vwap_distance_pct"))
    if relation == "above":
        vwap = 100.0 if distance <= 2.0 else max(20.0, 100.0 - (distance - 2) * 16)
    elif relation == "testing":
        vwap = 80.0
    else:
        vwap = max(0.0, 45.0 - distance * 15)

    confirmations = min(4.0, _number(record, "timeframe_confirmations"))
    trend = (
        (45.0 if record.get("supertrend_bullish") else 0.0)
        + (10.0 if record.get("supertrend_flip") else 0.0)
        + (25.0 if record.get("ema65_relation") == "above" else 0.0)
        + confirmations * 5.0
    )

    rvol = _number(record, "rvol_proxy", _number(record, "volume_pace_ratio"))
    relative_volume = _bounded(25.0 + 37.5 * math.log2(max(rvol, 0.5)))

    acceleration = _number(
        record, "acceleration_ratio", _number(record, "volume_acceleration", 1.0)
    )
    volume_acceleration = _bounded((acceleration - 0.5) * 100.0)

    # Near/above VWAP is high-quality extension; chasing progressively loses points.
    if relation == "above":
        extension = 100.0 if distance <= 2.0 else max(0.0, 100.0 - (distance - 2) * 20)
    elif relation == "testing":
        extension = 90.0
    else:
        extension = max(0.0, 60.0 - distance * 20)

    qualities = {
        "participation": participation,
        "structure": structure,
        "vwap_quality": vwap,
        "trend_confirmation": trend,
        "relative_volume": relative_volume,
        "volume_acceleration": volume_acceleration,
        "extension_quality": extension,
    }
    breakdown = {
        name: round(_bounded(qualities[name]) * weight / 100.0, 1)
        for name, weight in QUALITY_WEIGHTS.items()
    }
    score = int(round(_bounded(sum(breakdown.values()))))
    return {
        "quality_score": score,
        "quality_grade": quality_grade(score),
        "quality_score_breakdown": breakdown,
    }


def enrich_quality_score(record: dict) -> dict:
    record.update(calculate_quality_score(record))
    return record

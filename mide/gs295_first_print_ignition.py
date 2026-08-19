"""GS295 first-print structure ignition observation.

This is review urgency only. It never changes discovery membership, stage decisions,
scoring, ranking, readiness, entry triggers, or execution.
"""
from __future__ import annotations


def _number(record: dict, *keys: str) -> float | None:
    for key in keys:
        value = record.get(key)
        if value is not None:
            try:
                return float(value)
            except (TypeError, ValueError):
                continue
    return None


def first_print_ignition(record: dict) -> dict:
    """Identify a strict fresh-tape ignition that deserves immediate human review."""
    relation = str(record.get("vwap_relation") or "").lower()
    distance = _number(record, "vwap_distance_pct")
    vwap_supported = relation == "above" and (distance is None or distance <= 2.0)

    st_flip = bool(
        record.get("supertrend_30s_flip")
        or record.get("supertrend_flip")
        or record.get("supertrend_flipped_last_10m")
    )
    trend_supported = st_flip or bool(record.get("supertrend_bullish"))

    surge = record.get("participation_surge_diagnostics") or {}
    participation = _number(
        record, "participation_surge_score", "participation_score"
    )
    if participation is None:
        participation = _number(surge, "participation_score") or 0.0
    acceleration = _number(record, "volume_acceleration") or 0.0
    rvol = _number(record, "rvol_proxy", "rvol") or 0.0
    participation_hot = participation >= 60 or acceleration >= 2.0 or rvol >= 3.0

    breakout = bool(
        record.get("broke_previous_15m_high_with_volume")
        or record.get("breakout_confirmed")
        or record.get("crossed_vwap_and_supertrend")
    )
    recent_gain = _number(record, "price_change_10m_pct", "ten_minute_gain_pct") or 0.0
    pct_change = _number(record, "pct_change") or 0.0
    momentum_present = breakout or recent_gain >= 4.0 or pct_change >= 8.0

    # GS293 owns repeated-scan acceleration. GS295 covers only the complementary
    # first observation so the same condition cannot double-promote later scans.
    first_print = not bool(record.get("opportunity_pulse_previous"))
    not_extended = distance is None or distance <= 5.0

    promoted = bool(
        first_print
        and not_extended
        and vwap_supported
        and trend_supported
        and st_flip
        and participation_hot
        and momentum_present
    )
    return {
        "promoted": promoted,
        "first_print": first_print,
        "vwap_supported": vwap_supported,
        "trend_supported": trend_supported,
        "supertrend_flip": st_flip,
        "participation_hot": participation_hot,
        "participation_score": round(float(participation), 1),
        "volume_acceleration": round(float(acceleration), 2),
        "rvol": round(float(rvol), 2),
        "momentum_present": momentum_present,
        "breakout": breakout,
        "not_extended": not_extended,
    }

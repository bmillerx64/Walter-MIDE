"""Trader-facing entry timing state for live momentum setups.

This module does not discover or qualify symbols.  It classifies the current
entry phase after Walter has already found a candidate so an active correction
cannot be presented as an actionable entry.
"""
from __future__ import annotations


def _num(record: dict, *keys: str, default: float = 0.0) -> float:
    for key in keys:
        value = record.get(key)
        if value is not None:
            try:
                return float(value)
            except (TypeError, ValueError):
                pass
    return default


def classify_entry_state(record: dict, prior: dict | None = None) -> dict:
    prior = prior or {}
    relation = str(record.get("vwap_relation") or "").lower()
    above_vwap = relation == "above" or bool(record.get("price_above_vwap"))
    vwap_distance = _num(record, "vwap_distance_pct")
    bullish = bool(record.get("supertrend_bullish"))
    flipped = bool(record.get("supertrend_flip") or record.get("supertrend_flipped_last_10m"))
    higher_lows = bool(record.get("higher_lows"))
    pullback = bool(record.get("pullback") or record.get("reset_in_progress"))
    acceleration_1m = _num(record, "volume_acceleration_1m", "volume_acceleration")
    acceleration_3m = _num(record, "volume_acceleration_3m", "volume_acceleration")
    dollar_1m = _num(record, "dollar_flow_acceleration_1m")
    change_10m = _num(record, "price_change_10m_pct", "ten_minute_gain_pct")
    trigger = str(record.get("trigger") or "").upper() == "YES"

    prior_price = _num(prior, "price")
    price = _num(record, "price")
    price_reversing = bool(prior_price and price > prior_price)
    participation_reaccelerating = acceleration_1m > 1.15 and acceleration_1m >= acceleration_3m
    buyers_returning = price_reversing and participation_reaccelerating
    support_intact = above_vwap and bullish

    extended = above_vwap and (vwap_distance > 4.0 or change_10m > 12.0)
    correcting = pullback or (
        bool(prior)
        and price < prior_price
        and (acceleration_1m < acceleration_3m or acceleration_1m < 1.0)
    )
    reentry = (
        bool(prior)
        and support_intact
        and buyers_returning
        and (higher_lows or trigger or flipped)
        and not extended
    )
    ignition = (
        support_intact
        and (flipped or trigger)
        and acceleration_1m >= 1.5
        and max(acceleration_3m, dollar_1m) >= 1.25
        and not extended
        and not correcting
    )

    if extended:
        state, actionable, reason = "EXTENDED", False, "Move is stretched; wait for a reset."
    elif correcting and not reentry:
        state, actionable, reason = "CORRECTING", False, "Correction is still active; buyers have not reasserted control."
    elif reentry:
        state, actionable, reason = "RE-ENTRY CONFIRMED", True, "Support held and price/participation are turning back up."
    elif ignition:
        state, actionable, reason = "IGNITING", True, "Fresh trend confirmation is backed by expanding participation."
    else:
        state, actionable, reason = "WATCH", False, "Setup is developing but entry confirmation is incomplete."

    return {
        "entry_state": state,
        "entry_actionable": actionable,
        "entry_state_reason": reason,
        "entry_support_intact": support_intact,
        "entry_buyers_returning": buyers_returning,
        "entry_participation_reaccelerating": participation_reaccelerating,
    }

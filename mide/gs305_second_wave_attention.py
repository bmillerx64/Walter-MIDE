"""GS305: widen the Structure Engine's *attention* admission, not trading logic.

The existing early-setup engine is intentionally strict about timing.  That is
useful for entries but too strict for Walter's simpler job of saying "open this
chart."  GS305 adds a display-only attention path for major movers, second-wave
re-ignitions, and halt/suspension states.  It never changes discovery membership,
scoring, stage decisions, ranking, readiness, alerts, orders, or execution.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Callable


def _num(record: dict, *keys: str, default: float = 0.0) -> float:
    for key in keys:
        value = record.get(key)
        if value is not None:
            try:
                return float(value)
            except (TypeError, ValueError):
                continue
    return default


def attention_evaluation(record: dict) -> dict[str, Any]:
    """Classify whether Walter should put the chart in front of the trader now."""
    prior = record.get("opportunity_pulse_previous") or {}
    pct_change = _num(record, "pct_change")
    recent_gain = _num(record, "price_change_10m_pct", "ten_minute_gain_pct")
    distance = _num(record, "vwap_distance_pct", default=999.0)
    relation = str(record.get("vwap_relation") or "").lower()
    above_vwap = relation == "above"
    trend = bool(record.get("supertrend_bullish") or record.get("supertrend_flip"))
    breakout = bool(
        record.get("broke_previous_15m_high_with_volume")
        or record.get("breakout_confirmed")
    )
    acceleration = max(
        _num(record, "volume_acceleration"),
        _num(record, "acceleration_ratio", "five_minute_acceleration"),
    )
    rvol = _num(record, "rvol_proxy", "rvol")
    pace = bool(record.get("volume_above_preceding_15m_pace"))
    participation = acceleration >= 1.25 or rvol >= 2.0 or pace
    liquid = _num(record, "dollar_volume") >= 250_000

    market_status = " ".join(
        str(record.get(key) or "")
        for key in ("trading_status", "market_status", "status_text", "halt_status")
    ).lower()
    halted = bool(
        record.get("halted")
        or record.get("halt_detected")
        or record.get("suspended")
        or "halt" in market_status
        or "suspend" in market_status
    )

    # The MMA-type pattern: Walter has already seen the symbol, the first move did
    # not destroy VWAP/trend structure, and the tape starts expanding again.
    second_wave = bool(
        prior
        and pct_change >= 15
        and liquid
        and above_vwap
        and trend
        and participation
        and (breakout or recent_gain >= 4.0)
    )

    # Broad "this deserves a chart" fallback.  Deliberately easier than an entry
    # gate: a large mover with real liquidity plus tape/structure evidence belongs
    # on the attention screen even if Walter is already late.
    major_mover = bool(
        pct_change >= 20
        and liquid
        and (participation or breakout)
        and (above_vwap or trend)
    )

    eligible = halted or second_wave or major_mover
    if halted:
        label = "HALTED / WATCH RESUME"
    elif distance > 5:
        label = "CHASE / WAIT FOR RESET"
    elif second_wave:
        label = "LOOK NOW · RE-IGNITION"
    elif major_mover:
        label = "LOOK NOW · MAJOR MOVER"
    else:
        label = ""

    return {
        "eligible": eligible,
        "label": label,
        "halted": halted,
        "second_wave": second_wave,
        "major_mover": major_mover,
        "pct_change": round(pct_change, 2),
        "recent_gain_pct": round(recent_gain, 2),
        "vwap_distance_pct": round(distance, 2) if distance != 999.0 else None,
        "above_vwap": above_vwap,
        "trend_supported": trend,
        "participation_active": participation,
        "breakout": breakout,
    }


def install() -> None:
    """Install at the existing Structure Engine selection seam."""
    from . import early_setup

    if getattr(early_setup, "_gs305_installed", False):
        return

    original: Callable[[list[dict], int], list[dict]] = early_setup.top_timing_setups

    def top_timing_setups(records: list[dict], limit: int = 5) -> list[dict]:
        selected = list(original(records, limit=limit))
        selected_symbols = {
            str(record.get("symbol") or "").upper() for record in selected
        }
        additions = []
        for source in records:
            symbol = str(source.get("symbol") or "").upper()
            if not symbol or symbol in selected_symbols:
                continue
            attention = attention_evaluation(source)
            if not attention["eligible"]:
                continue
            record = deepcopy(source)
            detail = deepcopy(record.get("early_setup") or {})
            structure = deepcopy(record.get("structure") or detail.get("structure") or {})
            detail["attention"] = attention
            if attention["label"] == "CHASE / WAIT FOR RESET":
                detail["timing_state"] = "WAIT FOR RESET"
                detail.setdefault("percent_move_since_first_detection", attention["pct_change"])
            else:
                structure["state"] = attention["label"]
            detail["structure"] = structure
            record["early_setup"] = detail
            record["structure"] = structure
            record["walter_attention"] = attention
            additions.append(record)

        additions.sort(
            key=lambda r: (
                1 if (r.get("walter_attention") or {}).get("halted") else 0,
                1 if (r.get("walter_attention") or {}).get("second_wave") else 0,
                _num(r, "pct_change"),
                _num(r, "dollar_volume"),
            ),
            reverse=True,
        )
        return (selected + additions)[:limit]

    early_setup.top_timing_setups = top_timing_setups
    early_setup._gs305_top_timing_setups_original = original
    early_setup._gs305_installed = True

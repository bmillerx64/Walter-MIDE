"""GS462: surface the operator's pre-flip 30s -> 1m ignition watch.

Live RETO training on 2026-09-15 clarified the hierarchy:
- a recent bullish 30s SuperTrend flip above VWAP is the first cue;
- if 1m is already bullish above VWAP, or is only a small distance from its current
  SuperTrend line while above VWAP, the symbol deserves an EARLY WATCH;
- if 3m is likewise bullish/near above VWAP and participation/flow is healthy, that is
  additive JET FUEL, not a required gate for the early watch;
- 5m/10m continuation is a bonus only and must never become a prerequisite.

The provisional 2% near-ST band is an operator-attention calibration only. Exact gaps
are retained in the presentation so live validation can tighten/widen the band later.
This module adds no provider request, no indicator pass, no opportunity-state rewrite,
no entry/readiness/qualification authority, and no new audio. It only enriches the
existing trader-facing explanation and gives an operator-order lift below LOOK NOW.
"""
from __future__ import annotations

from copy import deepcopy
from functools import wraps
from typing import Any

NEAR_ST_LINE_PCT = 2.0
RECENT_30S_FLIP_SECONDS = 10 * 60.0
PRE_FLIP_ATTENTION_BAND = 39
_PROVENANCE = "PRE_FLIP_ST_IGNITION_WATCH"
_ORDER_OWNER_ATTR = "_walter_gs462_preflip_ignition_watch_owner"


def _number(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number


def _gap_pct(close: float | None, st_value: float | None) -> float | None:
    close = _number(close)
    st_value = _number(st_value)
    if close in (None, 0) or st_value is None:
        return None
    return abs(st_value - close) / close * 100.0


def _timeframe_detail(record: dict, label: str) -> dict:
    timeframes = record.get("timeframes") or {}
    detail = dict(timeframes.get(label) or {})
    line_cross = dict(detail.get("st_vwap_line_cross") or {})

    if label == "30s":
        alignment = dict((record.get("timeframe_alignment") or {}).get("30s") or {})
        tripwire = dict(record.get("thirty_second_tripwire") or {})
        close = (
            _number(tripwire.get("latest_close"))
            or _number(detail.get("current_close"))
            or _number(record.get("price"))
        )
        st_value = (
            _number(alignment.get("supertrend_value"))
            or _number(detail.get("supertrend_value"))
            or _number(line_cross.get("latest_supertrend_value"))
        )
        vwap = (
            _number(alignment.get("vwap_value"))
            or _number(detail.get("vwap_value"))
            or _number(record.get("vwap_30s_value"))
        )
        above_vwap = bool(
            alignment.get("above_vwap")
            if "above_vwap" in alignment
            else (close is not None and vwap is not None and close >= vwap)
        )
        bullish = bool(
            record.get("supertrend_30s_bullish")
            or alignment.get("supertrend_bullish")
            or detail.get("current_supertrend_bullish")
            or detail.get("supertrend")
        )
        age = (
            _number(record.get("supertrend_30s_last_flip_age_seconds"))
            if record.get("supertrend_30s_last_flip_age_seconds") is not None
            else _number(tripwire.get("last_flip_age_seconds"))
        )
        return {
            "timeframe": label,
            "available": bool(close is not None and (st_value is not None or bullish)),
            "bullish": bullish,
            "above_vwap": above_vwap,
            "current_close": close,
            "current_supertrend": st_value,
            "current_vwap": vwap,
            "st_gap_pct": round(_gap_pct(close, st_value), 3) if _gap_pct(close, st_value) is not None else None,
            "flip_age_seconds": age,
            "recent_flip": bool(
                bullish
                and age is not None
                and 0 <= age <= RECENT_30S_FLIP_SECONDS
            ),
        }

    close = _number(detail.get("current_close")) or _number(record.get("price"))
    st_value = _number(line_cross.get("latest_supertrend_value"))
    vwap = _number(detail.get("current_vwap")) or _number(line_cross.get("latest_vwap_value"))
    bullish = bool(detail.get("current_supertrend_bullish") or detail.get("supertrend"))
    above_vwap = bool(
        detail.get("current_above_vwap")
        if "current_above_vwap" in detail
        else detail.get("above_vwap")
    )
    gap = _gap_pct(close, st_value)
    near = bool(not bullish and gap is not None and gap <= NEAR_ST_LINE_PCT)
    return {
        "timeframe": label,
        "available": bool(close is not None and (st_value is not None or bullish)),
        "bullish": bullish,
        "above_vwap": above_vwap,
        "current_close": close,
        "current_supertrend": st_value,
        "current_vwap": vwap,
        "st_gap_pct": round(gap, 3) if gap is not None else None,
        "near_supertrend": near,
        "supportive": bool(above_vwap and (bullish or near)),
    }


def preflip_ignition_watch(record: dict) -> dict:
    """Return the early-watch / 3m-jet-fuel hierarchy without entry authority."""
    from . import gs459_price_trajectory_attention as gs459

    thirty = _timeframe_detail(record, "30s")
    one = _timeframe_detail(record, "1m")
    three = _timeframe_detail(record, "3m")
    five = _timeframe_detail(record, "5m")
    ten = _timeframe_detail(record, "10m")

    seed = bool(
        thirty.get("recent_flip")
        and thirty.get("above_vwap")
        and one.get("supportive")
    )
    flow = bool(gs459._supporting_flow(record))
    jet_fuel = bool(seed and three.get("supportive") and flow)
    bonus = [
        label
        for label, detail in (("5m", five), ("10m", ten))
        if detail.get("bullish") and detail.get("above_vwap")
    ]

    return {
        "active": seed,
        "stage": "JET FUEL" if jet_fuel else "EARLY WATCH" if seed else "NONE",
        "thirty_second": thirty,
        "one_minute": one,
        "three_minute": three,
        "five_minute": five,
        "ten_minute": ten,
        "supporting_flow": flow,
        "jet_fuel": jet_fuel,
        "bonus_continuation": bonus,
        "near_st_line_limit_pct": NEAR_ST_LINE_PCT,
        "authority": "OPERATOR_ATTENTION_ONLY",
        "entry_authority_changed": False,
        "three_minute_required_for_watch": False,
        "five_ten_required": False,
        "new_audio_added": False,
    }


def _tf_phrase(label: str, detail: dict) -> str:
    if detail.get("bullish"):
        return f"{label} bullish above VWAP"
    gap = _number(detail.get("st_gap_pct"))
    if detail.get("near_supertrend") and gap is not None:
        return f"{label} ST line {gap:.1f}% away above VWAP"
    return f"{label} not supportive"


def _state_with_preflip(original, record: dict) -> dict:
    from . import gs310_unified_opportunity_state as unified

    base = original(record)
    signal = preflip_ignition_watch(record)
    if not signal.get("active") or base.get("state") == unified.HALTED:
        return base

    view = deepcopy(base)
    provenance = list(view.get("attention_provenance") or [])
    if _PROVENANCE not in provenance:
        provenance.append(_PROVENANCE)
    view["attention_provenance"] = provenance
    view["preflip_ignition_watch"] = signal

    one_text = _tf_phrase("1m", signal["one_minute"])
    thirty = signal["thirty_second"]
    reason_add = f"EARLY ST WATCH: recent 30s bullish flip above VWAP; {one_text}."
    if signal.get("jet_fuel"):
        reason_add += f" JET FUEL: {_tf_phrase('3m', signal['three_minute'])} with supportive participation/flow."
    elif signal["three_minute"].get("supportive"):
        reason_add += f" 3m is supportive, but participation/flow is not yet strong enough for the jet-fuel label."
    bonus = list(signal.get("bonus_continuation") or [])
    if bonus:
        reason_add += " Bonus continuation: " + "/".join(bonus) + " bullish above VWAP."

    reason = str(view.get("reason") or "").rstrip()
    if "EARLY ST WATCH:" not in reason:
        view["reason"] = f"{reason} {reason_add}".strip()
    next_step = str(view.get("next_step") or "").rstrip()
    if "30s/1m watch" not in next_step:
        view["next_step"] = (
            f"{next_step} Treat this as a 30s/1m watch only. 3m adds jet fuel; 5m/10m are bonuses, "
            "not gates. Existing readiness, VWAP anti-chase and execution rules remain authoritative."
        ).strip()
    return view


def effective_attention_band(record: dict) -> int:
    """Lift a valid early watch below LOOK NOW, without changing opportunity state."""
    from . import gs459_price_trajectory_attention as gs459

    base = int(gs459.effective_attention_band(record))
    if preflip_ignition_watch(record).get("active"):
        return max(base, PRE_FLIP_ATTENTION_BAND)
    return base


def ordered_preflip_records(records: list[dict], baseline_order=None) -> list[dict]:
    """Preserve established order except for the bounded early-watch attention lift."""
    from . import gs459_price_trajectory_attention as gs459

    baseline = (
        list(baseline_order(records))
        if baseline_order is not None
        else gs459.ordered_trajectory_records(records)
    )

    def tie_key(record: dict) -> tuple:
        detail = preflip_ignition_watch(record)
        if not detail.get("active"):
            return (0, float("-inf"), float("-inf"))
        one_gap = _number((detail.get("one_minute") or {}).get("st_gap_pct"))
        three_gap = _number((detail.get("three_minute") or {}).get("st_gap_pct"))
        return (
            1 if detail.get("jet_fuel") else 0,
            -(one_gap if one_gap is not None else 999.0),
            -(three_gap if three_gap is not None else 999.0),
        )

    baseline.sort(key=tie_key, reverse=True)
    baseline.sort(key=effective_attention_band, reverse=True)
    return baseline


def _inherit(wrapper, wrapped) -> None:
    for name, value in getattr(wrapped, "__dict__", {}).items():
        if name.startswith("_gs") and not hasattr(wrapper, name):
            setattr(wrapper, name, value)


def _install_state() -> None:
    from . import gs310_unified_opportunity_state as unified
    from . import gs311_unified_voice as voice
    from . import gs314_state_consistency as consistency
    from . import gs363_operator_attention_hierarchy as hierarchy

    current = unified.opportunity_state
    if getattr(current, "_gs462_preflip_ignition_watch", False):
        calibrated = current
    else:
        @wraps(current)
        def calibrated(record: dict) -> dict:
            return _state_with_preflip(current, record)

        _inherit(calibrated, current)
        calibrated._gs462_preflip_ignition_watch = True
        calibrated._gs462_original = current
        unified.opportunity_state = calibrated

    voice.opportunity_state = calibrated
    consistency.opportunity_state = calibrated
    hierarchy.opportunity_state = calibrated


def _install_order() -> None:
    from . import gs369_escalation_priority_order as gs369

    current = gs369.ordered_escalation_records
    if getattr(current, _ORDER_OWNER_ATTR, False):
        return

    def ordered_escalation_records(records: list[dict]) -> list[dict]:
        return ordered_preflip_records(records, baseline_order=current)

    _inherit(ordered_escalation_records, current)
    ordered_escalation_records._gs462_preflip_ignition_watch = True
    ordered_escalation_records._gs462_original = current
    setattr(ordered_escalation_records, _ORDER_OWNER_ATTR, True)
    gs369.ordered_escalation_records = ordered_escalation_records


def install() -> None:
    """Install presentation-only pre-flip attention after the GS460/461 layers."""
    _install_state()
    _install_order()

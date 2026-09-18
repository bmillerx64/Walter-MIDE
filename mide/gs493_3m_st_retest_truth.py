"""GS493: make 3-minute SuperTrend retest truth explicit.

Sep. 18 TRUG live validation exposed an operator-interpretation failure. The intended
setup was a 3m SuperTrend retest, but a pullback to VWAP was treated as if it satisfied
that setup while the actual 3m ST line remained materially lower. The trade was entered
before the stated setup occurred.

GS493 reuses GS462's established 2% near-ST attention band and adds presentation-only
truth to every visible Opportunity State when a current 3m ST line is available:

* ST RETEST CONFIRMED: current price is on/above the bullish 3m ST line and within 2%.
* NOT AT 3M ST YET: 3m remains bullish but current price is still >2% above the line.
* 3M ST LOST / RECLAIM WATCH: 3m is no longer bullish or price is below the ST line.

The exact current price, current 3m ST value, and signed percentage gap are shown.
VWAP contact is explicitly stated not to substitute for a 3m ST retest.

No discovery, market data, indicator formulas, scoring, ranking, qualification,
readiness, anti-chase, alerts, execution, or orders change.
"""
from __future__ import annotations

from copy import deepcopy
from functools import wraps
from typing import Any

from .gs462_preflip_ignition_watch import NEAR_ST_LINE_PCT, _timeframe_detail

_OWNER = "_walter_gs493_3m_st_retest_truth"


def _number(value: Any) -> float | None:
    try:
        return float(value) if value is not None and value != "" else None
    except (TypeError, ValueError):
        return None


def _decision(record: dict) -> dict:
    value = record.get("decision_time_evidence") or {}
    return value if isinstance(value, dict) else {}


def _field(record: dict, key: str, default=None):
    if key in record and record.get(key) is not None:
        return record.get(key)
    return _decision(record).get(key, default)


def _fmt_price(value: float | None) -> str:
    if value is None:
        return "n/a"
    if abs(value) < 1:
        return f"{value:.4f}"
    if abs(value) < 10:
        return f"{value:.3f}"
    return f"{value:.2f}"


def three_minute_st_retest_truth(record: dict) -> dict:
    detail = _timeframe_detail(record, "3m")
    price = _number(_field(record, "price"))
    st_value = _number(detail.get("current_supertrend"))
    bullish = bool(detail.get("bullish"))
    available = bool(detail.get("available") and price is not None and st_value is not None)

    signed_gap = None
    if available and price not in (None, 0):
        signed_gap = (price - st_value) / price * 100.0

    state = "UNAVAILABLE"
    if available:
        if not bullish or (signed_gap is not None and signed_gap < 0.0):
            state = "3M_ST_LOST"
        elif signed_gap is not None and signed_gap <= NEAR_ST_LINE_PCT:
            state = "ST_RETEST_CONFIRMED"
        else:
            state = "NOT_AT_3M_ST_YET"

    return {
        "available": available,
        "state": state,
        "price": price,
        "three_minute_supertrend": st_value,
        "signed_gap_pct": round(signed_gap, 3) if signed_gap is not None else None,
        "near_st_line_limit_pct": NEAR_ST_LINE_PCT,
        "three_minute_bullish": bullish,
        "authority": "PRESENTATION_GUARDRAIL_ONLY",
        "entry_authority_changed": False,
        "readiness_authority_changed": False,
    }


def _guardrail_text(truth: dict) -> str:
    price = _fmt_price(_number(truth.get("price")))
    st_value = _fmt_price(_number(truth.get("three_minute_supertrend")))
    gap = _number(truth.get("signed_gap_pct"))
    gap_text = "n/a" if gap is None else f"{abs(gap):.1f}%"

    if truth.get("state") == "ST_RETEST_CONFIRMED":
        return (
            f"3M ST RETEST CONFIRMED: price {price} is {gap_text} above the current "
            f"3m SuperTrend line {st_value}, inside Walter's existing "
            f"{NEAR_ST_LINE_PCT:.0f}% near-ST band."
        )
    if truth.get("state") == "3M_ST_LOST":
        relation = "below" if gap is not None and gap < 0 else "at"
        return (
            f"3M ST LOST / RECLAIM WATCH: price {price} is {gap_text} {relation} the "
            f"current 3m SuperTrend line {st_value}, or the 3m trend state is bearish. "
            "A prior retest thesis is no longer confirmed."
        )
    if truth.get("state") == "NOT_AT_3M_ST_YET":
        return (
            f"NOT AT 3M ST YET: price {price} remains {gap_text} above the current "
            f"3m SuperTrend line {st_value}. A VWAP touch does NOT count as a 3m "
            "SuperTrend retest."
        )
    return ""


def state_with_3m_st_truth(original, record: dict) -> dict:
    base = original(record)
    truth = three_minute_st_retest_truth(record)
    if not truth.get("available"):
        return base

    view = deepcopy(base)
    view["three_minute_st_retest_truth"] = truth
    guardrail = _guardrail_text(truth)
    if not guardrail:
        return view

    next_step = str(view.get("next_step") or "").strip()
    if guardrail not in next_step:
        view["next_step"] = f"{guardrail} {next_step}".strip()
    return view


def _inherit(wrapper, wrapped) -> None:
    for name, value in getattr(wrapped, "__dict__", {}).items():
        if name.startswith("_gs") and not hasattr(wrapper, name):
            setattr(wrapper, name, value)


def install() -> None:
    """Install the final visual 3m ST-retest guardrail across Opportunity State bindings."""
    from . import gs310_unified_opportunity_state as unified
    from . import gs311_unified_voice as voice
    from . import gs314_state_consistency as consistency
    from . import gs363_operator_attention_hierarchy as hierarchy

    current = unified.opportunity_state
    if getattr(current, _OWNER, False):
        calibrated = current
    else:
        @wraps(current)
        def calibrated(record: dict) -> dict:
            return state_with_3m_st_truth(current, record)

        _inherit(calibrated, current)
        calibrated._gs493_3m_st_retest_truth = True
        calibrated._gs493_original = current
        setattr(calibrated, _OWNER, True)
        unified.opportunity_state = calibrated

    voice.opportunity_state = calibrated
    consistency.opportunity_state = calibrated
    hierarchy.opportunity_state = calibrated

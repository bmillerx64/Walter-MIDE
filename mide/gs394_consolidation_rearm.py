"""GS394: re-arm previously extended movers after a constructive consolidation reset.

Live validation on GCDT (2026-09-08) exposed a gap left intentionally intact by GS393:
Walter correctly refused a vertical chase, but after roughly 30 minutes of digestion the
1-minute SuperTrend flipped bullish again while the 3-minute structure remained bullish.
Because price was still well above VWAP, the +2% ignition guard continued to suppress
LOOK NOW even though the *risk geometry had reset through time and structure*.

GS394 does not loosen entry/readiness/execution thresholds.  It adds a chart-review-only
re-arm path for a narrow pattern:
* price remains above extended-session VWAP but no more than 10% above it;
* 1m SuperTrend has just flipped bullish and price is above VWAP;
* 3m is already bullish and above VWAP (confirmation, not permission);
* the preceding short sequence was compressed and the current candle expands from it;
* participation/expansion and fresh volume or dollar flow are present;
* 10-minute price change is not already vertical.

When those conditions are met, CHASE / WAIT may become LOOK NOW for *chart review only*.
The existing anti-chase tradeability/entry locks remain authoritative underneath it.
"""
from __future__ import annotations

from copy import deepcopy
from statistics import median

REARM_MIN_VWAP_DISTANCE_PCT = 2.0
REARM_MAX_VWAP_DISTANCE_PCT = 10.0
REARM_FLIP_RECENT_SECONDS = 150.0
REARM_MAX_10M_PRICE_CHANGE_PCT = 6.0
REARM_MIN_PARTICIPATION = 40.0
REARM_MIN_EXPANSION = 55.0
REARM_MIN_VOLUME_ACCELERATION = 1.0
REARM_MIN_DOLLAR_FLOW_ACCELERATION_1M = 1.0
REARM_MAX_PRIOR_MEDIAN_RANGE_PCT = 3.5
REARM_MIN_RANGE_EXPANSION_MULTIPLE = 1.5


def _number(record: dict, *keys: str, default: float | None = None) -> float | None:
    for key in keys:
        value = record.get(key)
        if value is None or value == "":
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return default


def _timeframe(record: dict, name: str) -> dict:
    states = record.get("timeframes") or {}
    value = states.get(name) if isinstance(states, dict) else None
    return dict(value) if isinstance(value, dict) else {}


def _compressed_then_expanding(record: dict) -> tuple[bool, dict]:
    values = record.get("last_five_candle_ranges_pct") or []
    try:
        ranges = [float(v) for v in list(values)[-5:]]
    except (TypeError, ValueError):
        ranges = []
    if len(ranges) < 5:
        return False, {
            "last_five_ranges_pct": ranges,
            "prior_median_range_pct": None,
            "current_range_pct": ranges[-1] if ranges else None,
            "range_expansion_multiple": None,
        }

    prior = ranges[:-1]
    current = ranges[-1]
    prior_median = float(median(prior))
    multiple = current / prior_median if prior_median > 0 else 0.0
    passed = bool(
        prior_median <= REARM_MAX_PRIOR_MEDIAN_RANGE_PCT
        and multiple >= REARM_MIN_RANGE_EXPANSION_MULTIPLE
    )
    return passed, {
        "last_five_ranges_pct": ranges,
        "prior_median_range_pct": round(prior_median, 4),
        "current_range_pct": round(current, 4),
        "range_expansion_multiple": round(multiple, 4),
    }


def consolidation_rearm_evidence(record: dict) -> dict:
    one = _timeframe(record, "1m")
    three = _timeframe(record, "3m")

    distance = _number(record, "vwap_distance_pct")
    relation = str(record.get("vwap_relation") or "").strip().lower()
    extended_but_bounded = bool(
        relation == "above"
        and distance is not None
        and REARM_MIN_VWAP_DISTANCE_PCT < distance <= REARM_MAX_VWAP_DISTANCE_PCT
    )

    one_bullish = bool(one.get("supertrend"))
    one_above_vwap = bool(one.get("above_vwap"))
    three_confirmed = bool(three.get("supertrend") and three.get("above_vwap"))

    flip_age = _number(record, "supertrend_flip_age_seconds")
    flip_recent = bool(
        flip_age is not None and 0.0 <= flip_age <= REARM_FLIP_RECENT_SECONDS
    )
    reclaim_recent = bool(record.get("vwap_reclaimed_last_10m"))

    price_change_10m = abs(_number(record, "price_change_10m_pct", default=999.0) or 999.0)
    not_vertical_now = price_change_10m <= REARM_MAX_10M_PRICE_CHANGE_PCT

    participation = _number(record, "participation_score", default=0.0) or 0.0
    expansion = _number(record, "expansion_score", "expansion_quality", default=0.0) or 0.0
    volume_accel = _number(record, "volume_acceleration", default=0.0) or 0.0
    dollar_flow_1m = _number(record, "dollar_flow_acceleration_1m", default=0.0) or 0.0

    participation_ok = participation >= REARM_MIN_PARTICIPATION
    expansion_ok = expansion >= REARM_MIN_EXPANSION
    fresh_flow = bool(
        volume_accel >= REARM_MIN_VOLUME_ACCELERATION
        or dollar_flow_1m >= REARM_MIN_DOLLAR_FLOW_ACCELERATION_1M
    )
    range_reset, range_detail = _compressed_then_expanding(record)

    recent = all(
        (
            extended_but_bounded,
            one_bullish,
            one_above_vwap,
            three_confirmed,
            flip_recent,
            reclaim_recent,
            not_vertical_now,
            participation_ok,
            expansion_ok,
            fresh_flow,
            range_reset,
        )
    )

    return {
        "recent": recent,
        "trigger": "CONSOLIDATION_REARM_1M" if recent else None,
        "chart_review_only": True,
        "entry_chase_guard_still_authoritative": True,
        "vwap_distance_pct": distance,
        "extended_but_bounded": extended_but_bounded,
        "one_minute_supertrend_bullish": one_bullish,
        "one_minute_above_vwap": one_above_vwap,
        "three_minute_confirmation": three_confirmed,
        "one_minute_bullish_flip_recent": flip_recent,
        "one_minute_bullish_flip_age_seconds": flip_age,
        "vwap_reclaimed_last_10m": reclaim_recent,
        "price_change_10m_pct": price_change_10m,
        "not_vertical_now": not_vertical_now,
        "participation_score": participation,
        "participation_ok": participation_ok,
        "expansion_score": expansion,
        "expansion_ok": expansion_ok,
        "volume_acceleration": volume_accel,
        "dollar_flow_acceleration_1m": dollar_flow_1m,
        "fresh_flow": fresh_flow,
        "range_reset": range_reset,
        "range_detail": range_detail,
    }


def _state_with_rearm(original, record: dict) -> dict:
    from . import gs310_unified_opportunity_state as unified

    base = original(record)
    evidence = consolidation_rearm_evidence(record)
    if not evidence["recent"]:
        return base
    if base.get("state") in {unified.WATCH_FOR_ENTRY, unified.HALTED}:
        return base

    view = deepcopy(base)
    view["state"] = unified.LOOK_NOW
    view["color"] = unified.STATE_COLORS[unified.LOOK_NOW]
    view["reason"] = (
        "Consolidation re-arm: 1m SuperTrend flipped bullish after a compressed reset "
        "while 3m structure remains confirmed."
    )
    view["next_step"] = (
        "Open the chart now. This is a re-arm review, not permission to chase; existing "
        "entry/readiness locks remain authoritative."
    )
    provenance = list(view.get("attention_provenance") or [])
    if "CONSOLIDATION_REARM_1M" not in provenance:
        provenance.append("CONSOLIDATION_REARM_1M")
    view["attention_provenance"] = provenance
    view["consolidation_rearm"] = evidence
    return view


def _install_state() -> None:
    from . import gs310_unified_opportunity_state as unified
    from . import gs311_unified_voice as voice
    from . import gs314_state_consistency as consistency
    from . import gs363_operator_attention_hierarchy as hierarchy

    current = unified.opportunity_state
    if getattr(current, "_gs394_consolidation_rearm", False):
        calibrated = current
    else:
        original = current

        def calibrated(record: dict) -> dict:
            return _state_with_rearm(original, record)

        for name, value in getattr(current, "__dict__", {}).items():
            if name.startswith("_gs") and not hasattr(calibrated, name):
                setattr(calibrated, name, value)
        calibrated._gs394_consolidation_rearm = True
        calibrated._gs394_original = original
        unified.opportunity_state = calibrated

    voice.opportunity_state = calibrated
    consistency.opportunity_state = calibrated
    hierarchy.opportunity_state = calibrated


def _install_recorder() -> None:
    from . import gs390_st_vwap_validation_sequence as sequence

    current = sequence.build_validation_sequence
    if getattr(current, "_gs394_consolidation_rearm", False):
        return

    def build_with_rearm(scan: dict, records, provider) -> dict:
        payload = dict(current(scan, records, provider))
        observations = []
        by_symbol = {
            str(item.get("symbol") or "").upper(): item
            for item in list(payload.get("symbols") or [])
            if isinstance(item, dict) and str(item.get("symbol") or "").strip()
        }
        for source in records or []:
            record = dict(source)
            symbol = str(record.get("symbol") or "").strip().upper()
            if not symbol:
                continue
            evidence = consolidation_rearm_evidence(record)
            if not evidence.get("recent"):
                continue
            observations.append({"symbol": symbol, "evidence": evidence})
            if symbol in by_symbol:
                by_symbol[symbol]["consolidation_rearm"] = evidence
        payload["consolidation_rearm_observations"] = observations
        payload["consolidation_rearm_count"] = len(observations)
        payload["consolidation_rearm_role"] = "LOOK_NOW_CHART_REVIEW_ONLY"
        return payload

    build_with_rearm._gs394_consolidation_rearm = True
    build_with_rearm._gs394_original = current
    sequence.build_validation_sequence = build_with_rearm


def install() -> None:
    _install_state()
    _install_recorder()

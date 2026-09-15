"""GS460: recognize bottom-up SuperTrend flip-price compression as ignition potential.

RETO live training on 2026-09-15 clarified the operator's actual entry thesis. The
sparkline was only the attention cue. The stronger signal began at the bottom of the
timeframe ladder: a 30s momentum turn, then 1m/3m/5m bullish SuperTrend flips whose
*prices* were close together while buy-in/flow remained present. Slower frames were
supporting context, not the starting condition.

GS460 teaches Walter that same sequence without creating entry authority:

    30s -> 1m -> 3m -> 5m flip-price compression + supporting flow = LOOK NOW

Two consecutive compressed rungs are enough for an early investigation signal;
three/four rungs increase the urgency. Existing 10m/15m state is retained only as
context. The signal is session-agnostic, so premarket can build evidence that the
operator cannot practically monitor by hand. Existing market-hours/readiness/order
rules remain authoritative and after-hours evidence never grants execution.

This layer adds no provider request and no new SuperTrend calculation. It reads the
30s tripwire plus the already-computed GS455/GS421 timeframe evidence. A fresh newly
joined rung can own the existing tier-2 LOOK NOW audio path, which is already
acoustically distinct from routine scanning and tier-3 entry urgency.
"""
from __future__ import annotations

from copy import deepcopy
from functools import wraps
from statistics import median
from typing import Any

EARLY_LADDER = ("30s", "1m", "3m", "5m")
_LATER_CONTEXT = ("10m", "15m")
_RECENT_SECONDS = {
    "30s": 12 * 60.0,
    "1m": 18 * 60.0,
    "3m": 28 * 60.0,
    "5m": 40 * 60.0,
}
_NEW_SECONDS = {
    "30s": 90.0,
    "1m": 120.0,
    "3m": 240.0,
    "5m": 360.0,
}
# Wider charts naturally flip at slightly different prices. These are attention
# tolerances, not entry thresholds.
_MAX_CLUSTER_SPAN_PCT = {2: 5.0, 3: 7.0, 4: 9.0}
LOOK_NOW_MAX_VWAP_DISTANCE_PCT = 5.0
_PROVENANCE = "ST_FLIP_PRICE_COMPRESSION"


def _number(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number


def _tf_detail(record: dict, label: str) -> dict:
    if label == "30s":
        tripwire = dict(record.get("thirty_second_tripwire") or {})
        return {
            "timeframe": "30s",
            "price_at_flip": (
                _number(record.get("supertrend_30s_last_flip_price"))
                or _number(tripwire.get("last_flip_price"))
            ),
            "age_seconds": (
                _number(record.get("supertrend_30s_last_flip_age_seconds"))
                if record.get("supertrend_30s_last_flip_age_seconds") is not None
                else _number(tripwire.get("last_flip_age_seconds"))
            ),
            "current_bullish": bool(
                record.get("supertrend_30s_bullish")
                or tripwire.get("bullish")
                or tripwire.get("supertrend_bullish")
            ),
            "timestamp": (
                record.get("supertrend_30s_last_flip_timestamp")
                or tripwire.get("last_flip_timestamp")
            ),
        }

    timeframes = record.get("timeframes") or {}
    detail = dict(timeframes.get(label) or {})
    if label == "15m" and not detail:
        maturation = record.get("multitimeframe_maturation") or {}
        detail = dict((maturation.get("timeframes") or {}).get(label) or {})
    return {
        "timeframe": label,
        "price_at_flip": _number(detail.get("price_at_flip")),
        "age_seconds": _number(detail.get("bullish_flip_age_seconds")),
        "current_bullish": bool(
            detail.get("current_supertrend_bullish")
            or detail.get("supertrend")
        ),
        "timestamp": detail.get("bullish_flip_timestamp"),
        "current_close": _number(detail.get("current_close")),
        "line_cross": dict(detail.get("st_vwap_line_cross") or {}),
    }


def _consecutive_recent_rungs(record: dict) -> list[dict]:
    """Return the consecutive bullish 30s->5m flip sequence that is still recent."""
    rungs: list[dict] = []
    for label in EARLY_LADDER:
        detail = _tf_detail(record, label)
        price = detail.get("price_at_flip")
        age = detail.get("age_seconds")
        if (
            price is None
            or price <= 0
            or age is None
            or age < 0
            or age > _RECENT_SECONDS[label]
            or not detail.get("current_bullish")
        ):
            break
        rungs.append(detail)
    return rungs


def _cluster_span_pct(prices: list[float]) -> float | None:
    if len(prices) < 2:
        return None
    center = median(prices)
    if center <= 0:
        return None
    return (max(prices) - min(prices)) / center * 100.0


def _supporting_flow(record: dict) -> bool:
    from . import gs455_early_ignition_3m_confirmation as gs455

    return bool(gs455._supporting_flow(record))


def _next_frame_context(record: dict, depth: int) -> dict:
    """Describe the next slower chart without making it part of signal authority."""
    if depth < 2:
        return {}
    next_label = {2: "3m", 3: "5m", 4: "10m"}.get(depth)
    if not next_label:
        return {}
    detail = _tf_detail(record, next_label)
    line_cross = detail.get("line_cross") or {}
    current_close = detail.get("current_close")
    st_value = _number(line_cross.get("latest_supertrend_value"))
    gap = None
    if current_close not in (None, 0) and st_value is not None:
        gap = abs(st_value - current_close) / current_close * 100.0
    return {
        "timeframe": next_label,
        "already_bullish": bool(detail.get("current_bullish")),
        "distance_to_supertrend_pct": round(gap, 3) if gap is not None else None,
    }


def st_flip_compression(record: dict) -> dict:
    """Return bottom-up flip-price compression evidence for operator attention."""
    rungs = _consecutive_recent_rungs(record)
    depth = len(rungs)
    prices = [float(item["price_at_flip"]) for item in rungs]
    span = _cluster_span_pct(prices)
    limit = _MAX_CLUSTER_SPAN_PCT.get(depth)
    compressed = bool(depth >= 2 and span is not None and limit is not None and span <= limit)
    flow = _supporting_flow(record)
    active = bool(compressed and flow)

    highest = rungs[-1] if rungs else {}
    highest_label = str(highest.get("timeframe") or "")
    highest_age = _number(highest.get("age_seconds"))
    fresh_join = bool(
        active
        and highest_label in _NEW_SECONDS
        and highest_age is not None
        and highest_age <= _NEW_SECONDS[highest_label]
    )

    stage = {
        0: "NONE",
        1: "SEED",
        2: "EARLY IGNITION",
        3: "IGNITION BUILDING",
        4: "IGNITION CASCADE",
    }.get(depth, "NONE")
    later_bullish = [
        label for label in _LATER_CONTEXT if _tf_detail(record, label).get("current_bullish")
    ]

    return {
        "active": active,
        "fresh_join": fresh_join,
        "stage": stage,
        "depth": depth,
        "sequence": " -> ".join(item["timeframe"] for item in rungs),
        "flip_prices": {
            item["timeframe"]: round(float(item["price_at_flip"]), 6) for item in rungs
        },
        "cluster_span_pct": round(span, 3) if span is not None else None,
        "cluster_limit_pct": limit,
        "supporting_flow": flow,
        "highest_rung": highest_label or None,
        "highest_rung_age_seconds": highest_age,
        "next_frame": _next_frame_context(record, depth),
        "later_bullish_context": later_bullish,
        "authority": "OPERATOR_ATTENTION_ONLY",
        "entry_authority_changed": False,
    }


def _state_with_compression(original, record: dict) -> dict:
    from . import gs310_unified_opportunity_state as unified

    base = original(record)
    signal = st_flip_compression(record)
    if not signal.get("active"):
        return base
    if base.get("state") in {unified.HALTED, unified.WATCH_FOR_ENTRY}:
        return base

    view = deepcopy(base)
    provenance = list(view.get("attention_provenance") or [])
    if _PROVENANCE not in provenance:
        provenance.append(_PROVENANCE)
    view["attention_provenance"] = provenance
    view["st_flip_compression"] = signal

    span = signal.get("cluster_span_pct")
    sequence = signal.get("sequence") or "30s -> 1m"
    stage = str(signal.get("stage") or "IGNITION").upper()
    next_frame = signal.get("next_frame") or {}
    next_text = ""
    if next_frame.get("already_bullish"):
        next_text = f" {next_frame.get('timeframe')} is already bullish."
    elif next_frame.get("distance_to_supertrend_pct") is not None:
        next_text = (
            f" {next_frame.get('timeframe')} SuperTrend is about "
            f"{next_frame['distance_to_supertrend_pct']:.1f}% away."
        )

    distance = _number(record.get("vwap_distance_pct"))
    if distance is not None and distance > LOOK_NOW_MAX_VWAP_DISTANCE_PCT:
        view["state"] = unified.CHASE_WAIT
        view["color"] = unified.STATE_COLORS[unified.CHASE_WAIT]
        view["reason"] = (
            f"{stage}: {sequence} ST flip prices are compressed within {span:.1f}% "
            f"with supporting flow.{next_text} Price is already {distance:.1f}% above VWAP."
        )
        view["next_step"] = (
            "Open the chart now for ignition context, but DO NOT CHASE. Flip compression "
            "is attention evidence only; wait for the existing VWAP/readiness rules."
        )
        return view

    view["state"] = unified.LOOK_NOW
    view["color"] = unified.STATE_COLORS[unified.LOOK_NOW]
    view["reason"] = (
        f"{stage}: {sequence} ST flip prices are compressed within {span:.1f}% "
        f"with supporting flow.{next_text}"
    )
    view["next_step"] = (
        "Open the chart now. This bottom-up compression can precede a timeframe cascade, "
        "but it does not grant entry authority; normal readiness and anti-chase rules remain."
    )
    return view


def _compression_change(record: dict) -> dict | None:
    signal = st_flip_compression(record)
    if not signal.get("fresh_join"):
        return None
    symbol = str(record.get("symbol") or "").strip().upper()
    if not symbol:
        return None
    highest = str(signal.get("highest_rung") or "").upper()
    prices = signal.get("flip_prices") or {}
    fingerprint = ",".join(f"{label}:{prices.get(label)}" for label in EARLY_LADDER if label in prices)
    return {
        "symbol": symbol,
        "from": f"ST FLIP CLUSTER {fingerprint}",
        "to": f"IGNITION COMPRESSION {highest}",
    }


def _spoken(label: str) -> str:
    return {
        "30s": "30 second",
        "1m": "1 minute",
        "3m": "3 minute",
        "5m": "5 minute",
    }.get(label, label)


def _compression_phrase(records: list[dict]) -> str:
    choices = []
    for record in records or []:
        signal = st_flip_compression(record)
        if signal.get("fresh_join"):
            choices.append((int(signal.get("depth") or 0), record, signal))
    if not choices:
        return ""
    _depth, record, signal = max(choices, key=lambda item: item[0])
    symbol = str(record.get("symbol") or "Symbol").strip().upper() or "SYMBOL"
    highest = _spoken(str(signal.get("highest_rung") or ""))
    span = float(signal.get("cluster_span_pct") or 0.0)
    phrase = (
        f"{symbol}. LOOK NOW. Ignition compression. SuperTrend flips through {highest} "
        f"are clustered within {span:.1f} percent with supporting flow."
    )
    distance = _number(record.get("vwap_distance_pct"))
    if distance is not None and distance > LOOK_NOW_MAX_VWAP_DISTANCE_PCT:
        phrase += " Extended. Do not chase."
    return phrase


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
    if getattr(current, "_gs460_st_flip_compression", False):
        calibrated = current
    else:
        original = current

        @wraps(original)
        def calibrated(record: dict) -> dict:
            return _state_with_compression(original, record)

        _inherit(calibrated, current)
        calibrated._gs460_st_flip_compression = True
        calibrated._gs460_original = original
        unified.opportunity_state = calibrated

    voice.opportunity_state = calibrated
    consistency.opportunity_state = calibrated
    hierarchy.opportunity_state = calibrated


def _install_alerts() -> None:
    from . import escalation
    from .gs365_chime_semantic_classifier import semantic_chime_count

    current_changes = escalation.escalation_state_changes
    if not getattr(current_changes, "_gs460_st_flip_compression", False):
        @wraps(current_changes)
        def state_changes(records: list[dict]) -> list[dict]:
            rows = list(records or [])
            existing = list(current_changes(rows))
            additions = [change for row in rows if (change := _compression_change(row))]
            keys = {
                (
                    str(item.get("symbol") or "").upper(),
                    str(item.get("from") or ""),
                    str(item.get("to") or ""),
                )
                for item in existing
            }
            for change in additions:
                key = (change["symbol"], change["from"], change["to"])
                if key not in keys:
                    existing.append(change)
                    keys.add(key)
            return existing

        _inherit(state_changes, current_changes)
        state_changes._gs460_st_flip_compression = True
        state_changes._gs460_original = current_changes
        escalation.escalation_state_changes = state_changes

    current_phrase = escalation.escalation_alert_phrase
    if not getattr(current_phrase, "_gs460_st_flip_compression", False):
        @wraps(current_phrase)
        def alert_phrase(records: list[dict]) -> str:
            rows = list(records or [])
            existing = str(current_phrase(rows) or "")
            compression = _compression_phrase(rows)
            if not compression:
                return existing
            if existing and semantic_chime_count(existing) >= 3:
                return existing
            return compression

        _inherit(alert_phrase, current_phrase)
        alert_phrase._gs460_st_flip_compression = True
        alert_phrase._gs460_original = current_phrase
        escalation.escalation_alert_phrase = alert_phrase


def install() -> None:
    """Install bottom-up flip compression at the late operator-attention boundary."""
    _install_state()
    _install_alerts()

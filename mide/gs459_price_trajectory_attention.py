"""GS459: teach Walter to notice the accelerating price path the operator sees.

Live training on 2026-09-15 produced a clean human-labelled example: the operator
entered a 24-minute trade from the visible sparkline/path change and captured about
20%, while Walter had awareness of the symbol but did not surface the developing
move with equivalent urgency at the moment the path visibly accelerated.

Walter already downloads the needed 1-minute bars for every analyzed candidate.
GS459 extracts a small, provider-free price-path description from those same bars:
recent 3m/5m return, prior 7m velocity, recent 3m velocity, acceleration, five-close
persistence, and giveback from the recent high. It then adds a narrow operator-only
priority lift when an accelerating, persistent path is accompanied by existing flow
and constructive structure.

This is deliberately *not* entry authority. WATCH FOR ENTRY, fresh ST/VWAP
maturation, and ordinary LOOK NOW remain higher. A trajectory ignition sits below
LOOK NOW but above GS457's older confirmed/developing bands so Walter can say, in
effect, "this path just changed -- look at it" without chasing or weakening any
qualification rule.
"""
from __future__ import annotations

from typing import Any

TRAJECTORY_BAND = 38
_MIN_3M_CHANGE_PCT = 1.0
_MIN_ACCELERATION_PCT_PER_MIN = 0.20
_MIN_POSITIVE_CLOSE_RATIO = 0.60
_MAX_GIVEBACK_FROM_5M_HIGH_PCT = 1.50
_MIN_FLOW_ACCELERATION = 1.20
_MIN_PARTICIPATION_SCORE = 40.0

_DISCOVERY_OWNER_ATTR = "_walter_gs459_price_trajectory_metrics_owner"
_ORDER_OWNER_ATTR = "_walter_gs459_price_trajectory_attention_owner"


def _number(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _return_pct(start: float, end: float) -> float:
    if start == 0:
        return 0.0
    return (end / start - 1.0) * 100.0


def price_trajectory_metrics(frame) -> dict:
    """Describe sparkline-like path acceleration from existing 1-minute bars."""
    defaults = {
        "price_trajectory_available": False,
        "price_change_3m_pct": 0.0,
        "price_change_5m_path_pct": 0.0,
        "price_change_prior_7m_pct": 0.0,
        "price_velocity_3m_pct_per_min": 0.0,
        "price_velocity_prior_7m_pct_per_min": 0.0,
        "price_path_acceleration_pct_per_min": 0.0,
        "positive_close_ratio_5m": 0.0,
        "giveback_from_5m_high_pct": 0.0,
    }
    try:
        if frame is None or len(frame) < 11:
            return defaults
        closes = frame["close"].astype(float).tail(11)
        highs = frame["high"].astype(float).tail(5)
    except Exception:
        return defaults
    if len(closes) < 11 or len(highs) < 1:
        return defaults

    current = float(closes.iloc[-1])
    three_start = float(closes.iloc[-4])
    five_start = float(closes.iloc[-6])
    prior_start = float(closes.iloc[-11])
    prior_end = float(closes.iloc[-4])

    change_3m = _return_pct(three_start, current)
    change_5m = _return_pct(five_start, current)
    prior_7m_change = _return_pct(prior_start, prior_end)
    recent_velocity = change_3m / 3.0
    prior_velocity = prior_7m_change / 7.0
    acceleration = recent_velocity - prior_velocity

    recent_closes = closes.tail(6)
    changes = recent_closes.diff().dropna()
    positive_ratio = (
        float((changes > 0).mean()) if len(changes) else 0.0
    )
    recent_high = float(highs.max())
    giveback = (
        max(0.0, (recent_high - current) / recent_high * 100.0)
        if recent_high > 0
        else 0.0
    )

    return {
        "price_trajectory_available": True,
        "price_change_3m_pct": round(change_3m, 3),
        "price_change_5m_path_pct": round(change_5m, 3),
        "price_change_prior_7m_pct": round(prior_7m_change, 3),
        "price_velocity_3m_pct_per_min": round(recent_velocity, 4),
        "price_velocity_prior_7m_pct_per_min": round(prior_velocity, 4),
        "price_path_acceleration_pct_per_min": round(acceleration, 4),
        "positive_close_ratio_5m": round(positive_ratio, 3),
        "giveback_from_5m_high_pct": round(giveback, 3),
    }


def _supporting_flow(record: dict) -> bool:
    participation = _number(
        record.get("participation_surge_score", record.get("participation_score", 0.0))
    )
    accelerations = (
        _number(record.get("volume_acceleration_3m", record.get("volume_acceleration", 0.0))),
        _number(record.get("volume_acceleration_5m", record.get("acceleration_ratio", 0.0))),
        _number(record.get("dollar_flow_acceleration_3m", 0.0)),
        _number(record.get("dollar_flow_acceleration_5m", record.get("dollar_flow_acceleration", 0.0))),
    )
    return bool(
        max(accelerations) >= _MIN_FLOW_ACCELERATION
        or participation >= _MIN_PARTICIPATION_SCORE
        or record.get("volume_above_preceding_15m_pace")
        or record.get("broke_previous_15m_high_with_volume")
    )


def trajectory_attention(record: dict) -> dict:
    """Return operator-only path-ignition evidence; never rewrite state/authority."""
    from . import gs310_unified_opportunity_state as unified

    state = str(unified.opportunity_state(record).get("state") or "")
    available = bool(record.get("price_trajectory_available"))
    change_3m = _number(record.get("price_change_3m_pct"))
    change_5m = _number(record.get("price_change_5m_path_pct"))
    acceleration = _number(record.get("price_path_acceleration_pct_per_min"))
    persistence = _number(record.get("positive_close_ratio_5m"))
    giveback = _number(record.get("giveback_from_5m_high_pct"), default=999.0)
    flow = _supporting_flow(record)
    structure = bool(record.get("higher_lows") or record.get("near_hod"))

    signal = bool(
        available
        and state != unified.HALTED
        and change_3m >= _MIN_3M_CHANGE_PCT
        and acceleration >= _MIN_ACCELERATION_PCT_PER_MIN
        and persistence >= _MIN_POSITIVE_CLOSE_RATIO
        and giveback <= _MAX_GIVEBACK_FROM_5M_HIGH_PCT
        and flow
        and structure
    )
    return {
        "active": signal,
        "state": state,
        "reason": "accelerating_price_path" if signal else "no_trajectory_ignition",
        "change_3m_pct": change_3m,
        "change_5m_pct": change_5m,
        "acceleration_pct_per_min": acceleration,
        "positive_close_ratio_5m": persistence,
        "giveback_from_5m_high_pct": giveback,
        "supporting_flow": flow,
        "structure_support": structure,
    }


def effective_attention_band(record: dict) -> int:
    """Insert trajectory ignition below LOOK NOW and above older/developing bands."""
    from . import gs457_maturation_leader_priority as gs457

    base = int(gs457.maturation_attention(record).get("band") or 0)
    if trajectory_attention(record).get("active"):
        return max(base, TRAJECTORY_BAND)
    return base


def ordered_trajectory_records(records: list[dict], baseline_order=None) -> list[dict]:
    """Preserve GS457 ordering except for the narrow trajectory priority lift."""
    from . import gs457_maturation_leader_priority as gs457

    baseline = (
        list(baseline_order(records))
        if baseline_order is not None
        else gs457.ordered_maturation_records(records)
    )

    def trajectory_tie(record: dict) -> tuple:
        detail = trajectory_attention(record)
        if not detail.get("active"):
            return (float("-inf"), float("-inf"), float("-inf"))
        return (
            float(detail.get("acceleration_pct_per_min") or 0.0),
            float(detail.get("change_3m_pct") or 0.0),
            float(detail.get("positive_close_ratio_5m") or 0.0),
        )

    # Python's stable sort preserves the complete GS457 order for equal keys.
    baseline.sort(key=trajectory_tie, reverse=True)
    baseline.sort(key=effective_attention_band, reverse=True)
    return baseline


def _install_discovery_metrics() -> None:
    from . import discovery

    current = discovery.intraday_participation_metrics
    if getattr(current, _DISCOVERY_OWNER_ATTR, False):
        return

    def intraday_participation_metrics(frame):
        result = dict(current(frame) or {})
        result.update(price_trajectory_metrics(frame))
        return result

    for name, value in getattr(current, "__dict__", {}).items():
        if name.startswith("_gs") and not hasattr(intraday_participation_metrics, name):
            setattr(intraday_participation_metrics, name, value)
    intraday_participation_metrics._gs459_price_trajectory_metrics = True
    intraday_participation_metrics._gs459_original = current
    setattr(intraday_participation_metrics, _DISCOVERY_OWNER_ATTR, True)
    discovery.intraday_participation_metrics = intraday_participation_metrics


def _install_operator_order() -> None:
    from . import gs369_escalation_priority_order as gs369

    current = gs369.ordered_escalation_records
    if getattr(current, _ORDER_OWNER_ATTR, False):
        return

    def ordered_escalation_records(records: list[dict]) -> list[dict]:
        return ordered_trajectory_records(records, baseline_order=current)

    for name, value in getattr(current, "__dict__", {}).items():
        if name.startswith("_gs") and not hasattr(ordered_escalation_records, name):
            setattr(ordered_escalation_records, name, value)
    ordered_escalation_records._gs459_price_trajectory_attention = True
    ordered_escalation_records._gs459_original = current
    setattr(ordered_escalation_records, _ORDER_OWNER_ATTR, True)
    gs369.ordered_escalation_records = ordered_escalation_records


def install() -> None:
    """Install bar evidence extraction and presentation-only trajectory priority."""
    _install_discovery_metrics()
    _install_operator_order()

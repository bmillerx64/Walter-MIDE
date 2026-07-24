from __future__ import annotations

from datetime import datetime, time, timezone
from zoneinfo import ZoneInfo
import logging
from numbers import Real

from mide.market_phase import apply_market_phase
from mide.trader_priority import (
    sortable_number as _sortable_number,
    trader_priority_sort_key,
)

logger = logging.getLogger(__name__)

STATE_RANK = {
    "Removed": 0,
    "Weakening": 1,
    "New": 2,
    "Watching": 3,
    "Emerging": 4,
    "Strengthening": 5,
    "Entry Ready": 6,
}

WATCH_STATES = {"Watching", "Emerging", "Strengthening", "Entry Ready"}
TIMED_STATES = {"Emerging", "Strengthening", "Entry Ready"}
TRANSITION_HISTORY_STATES = {"Emerging", "Watching", "Strengthening", "Entry Ready"}
MAX_TRANSITION_HISTORY = 4
PROMOTION_TARGET_STATES = {"Strengthening", "Entry Ready"}
STRENGTHENING_VWAP_MAX_BELOW_PCT = 1.0
MARKET_TZ = ZoneInfo("America/New_York")
BASE_MIN_VOLUME = 500_000
BASE_MIN_DOLLAR_VOLUME = 250_000
BASE_MIN_RVOL = 1.5
VPI_MIN_PACE_RATIO = 1.2
VPI_MIN_ACCELERATION_RATIO = 1.2
PARTICIPATION_MIN_ACCELERATION_RATIO = 1.2
PARTICIPATION_MIN_BUYING_EXPANSION = 1.1
SESSION_VOLUME_PROFILES = {
    "Pre-Market": 0.45,
    "Open": 1.6,
    "Midday": 0.75,
    "Power Hour": 1.25,
    "After Hours": 0.35,
}

STRENGTHENING_RULE_ORDER = ("News", "RVOL", "Dollar Volume", "VWAP", "SuperTrend")
STRENGTHENING_REJECTION_BUCKETS = (
    "Below VWAP",
    "RVOL",
    "SuperTrend",
    "Dollar Volume",
    "News",
    "Other",
)

__all__ = [
    "apply_scanner_v2",
    "classify_state",
    "momentum_evidence",
    "session_volume_diagnostics",
    "volume_pace_diagnostics",
    "state_elapsed_seconds",
    "strengthening_decision",
    "strengthening_diagnostics",
    "sequential_trend_confirmation",
    "participation_surge_diagnostics",
    "participation_gate_diagnostics",
    "participation_gate_rejection_diagnostics",
    "structure_gate_diagnostics",
    "momentum_quality_diagnostics",
    "trend_stability_diagnostics",
    "trigger_diagnostics",
]


def _ranked_record_sort_key(record: dict) -> tuple[float, float, str]:
    return trader_priority_sort_key(record)


def _has_strengthening_news(record: dict) -> bool:
    discovery = set(record.get("discovery_reasons") or [])
    return bool(record.get("headline") or "recent news" in discovery)


def _has_strengthening_supertrend(record: dict) -> bool:
    return bool(
        record.get("supertrend_flip")
        or record.get("supertrend_bullish")
        or _tf_supportive(record, "1m")
        or _tf_supportive(record, "3m")
    )


def _format_seconds(seconds: float) -> str:
    seconds = max(0, int(seconds))
    if seconds < 120:
        return f"{seconds} seconds"
    minutes = round(seconds / 60)
    return f"{minutes} minutes"


def _trigger_st_age_seconds(
    record: dict, scan_time: datetime | None = None
) -> int | None:
    for key in ("supertrend_30s_flip_age_seconds", "supertrend_flip_age_seconds"):
        if record.get(key) is not None:
            return max(0, int(_num(record, key)))
    events = record.get("trend_confirmation_events") or []
    thirty_second_events = [
        event
        for event in events
        if event.get("timeframe") == "30s" and event.get("confirmed_at")
    ]
    if not thirty_second_events or scan_time is None:
        return None
    try:
        confirmed_at = datetime.fromisoformat(
            str(thirty_second_events[-1]["confirmed_at"]).replace("Z", "+00:00")
        )
    except ValueError:
        return None
    if confirmed_at.tzinfo is None:
        confirmed_at = confirmed_at.replace(tzinfo=timezone.utc)
    if scan_time.tzinfo is None:
        scan_time = scan_time.replace(tzinfo=timezone.utc)
    return max(
        0,
        int(
            (
                scan_time.astimezone(timezone.utc)
                - confirmed_at.astimezone(timezone.utc)
            ).total_seconds()
        ),
    )


def trigger_diagnostics(
    record: dict, prior: dict | None = None, scan_time: datetime | None = None
) -> dict:
    """Evaluate Walter's single trigger rule set and explain pass/fail causes."""
    prior = prior or {}
    surge = record.get(
        "participation_surge_diagnostics"
    ) or participation_surge_diagnostics(record, prior, scan_time)
    vwap = record.get("strengthening_vwap_gate") or _current_vwap_diagnostics(
        record, prior
    )
    distance = float(vwap.get("distance_pct", _num(record, "vwap_distance_pct")) or 0)
    st_age = _trigger_st_age_seconds(record, scan_time)
    fresh_st = bool(record.get("supertrend_30s_flip", record.get("supertrend_flip")))
    st_passed = fresh_st and (st_age is None or st_age <= 180)
    surge_score = float(surge.get("participation_score", 0) or 0)
    quality = _num(record, "expansion_quality", surge.get("expansion_quality", 50))
    checks = [
        {
            "condition": "participation",
            "passed": surge_score >= 72,
            "passed_reason": f"Participation {surge_score / 13.333:.1f}×",
            "failed_reason": (
                "Participation declining"
                if surge_score < 55
                else f"Participation only {surge_score:.0f}/100"
            ),
        },
        {
            "condition": "supertrend_flip",
            "passed": st_passed,
            "passed_reason": (
                f"ST flipped {_format_seconds(st_age)} ago"
                if st_age is not None
                else "Fresh ST flip"
            ),
            "failed_reason": (
                f"ST flip occurred {_format_seconds(st_age)} ago"
                if fresh_st and st_age is not None
                else "No fresh ST flip"
            ),
        },
        {
            "condition": "vwap",
            "passed": 0 <= distance <= 2.0,
            "passed_reason": f"{abs(distance):.1f}% above VWAP",
            "failed_reason": (
                f"Price {abs(distance):.1f}% below VWAP"
                if distance < 0
                else f"Price {distance:.1f}% above VWAP"
            ),
        },
        {
            "condition": "not_extended",
            "passed": distance <= 2.0,
            "passed_reason": "Not extended",
            "failed_reason": "Extended above VWAP",
        },
        {
            "condition": "expansion_beginning",
            "passed": quality >= 58,
            "passed_reason": "Expansion beginning",
            "failed_reason": f"Expansion quality only {quality:.0f}/100",
        },
    ]
    failed = [check for check in checks if not check["passed"]]
    return {
        "trigger": "YES" if not failed else "NO",
        "passed": not failed,
        "checks": checks,
        "reasons": (
            [check["passed_reason"] for check in checks]
            if not failed
            else [check["failed_reason"] for check in failed]
        ),
        "failed_conditions": [check["condition"] for check in failed],
    }


def strengthening_decision(record: dict, scan_time: datetime | None = None) -> dict:
    """Explain the first observable rule that kept a symbol below Strengthening.

    This is diagnostic-only instrumentation. The scanner still uses the existing
    score/state rules; these checks mirror the major evidence buckets so tuning
    can see which bucket first goes missing.
    """
    volume_gate = record.get(
        "volume_session_diagnostics"
    ) or session_volume_diagnostics(record, scan_time)
    checks = [
        ("News", _has_strengthening_news(record), "News"),
        ("RVOL", volume_gate["rvol_passed"], "RVOL"),
        ("Dollar Volume", volume_gate["dollar_volume_passed"], "Dollar Volume"),
        (
            "VWAP",
            _strengthening_vwap_qualified(record),
            "Below VWAP",
        ),
        ("SuperTrend", _has_strengthening_supertrend(record), "SuperTrend"),
    ]
    state = record.get("candidate_status") or record.get("status")
    accepted = state in {"Strengthening", "Entry Ready"}
    first_failed = next(
        ((label, bucket) for label, passed, bucket in checks if not passed), None
    )
    return {
        "symbol": record.get("symbol", ""),
        "accepted": accepted,
        "status": (
            "Accepted for Strengthening" if accepted else "Rejected from Strengthening"
        ),
        "checks": [
            {"rule": label, "passed": bool(passed)} for label, passed, _bucket in checks
        ],
        "first_rejection_rule": (
            None if accepted else (first_failed[0] if first_failed else "Other")
        ),
        "first_rejection_bucket": (
            None if accepted else (first_failed[1] if first_failed else "Other")
        ),
        "candidate_status": state,
        "scanner_v2_score": record.get("scanner_v2_score"),
        "vwap_gate": record.get("strengthening_vwap_gate")
        or _current_vwap_diagnostics(record),
        "volume_gate": volume_gate,
        "volume_pace": volume_pace_diagnostics(record),
    }


def strengthening_diagnostics(records: list[dict]) -> dict:
    decisions = [strengthening_decision(record) for record in records]
    rejected = [decision for decision in decisions if not decision["accepted"]]
    by_rule = {bucket: 0 for bucket in STRENGTHENING_REJECTION_BUCKETS}
    for decision in rejected:
        bucket = decision.get("first_rejection_bucket") or "Other"
        by_rule[bucket if bucket in by_rule else "Other"] += 1
    return {
        "candidates_discovered": len(records),
        "candidates_rejected": len(rejected),
        "rejected_by_rule": by_rule,
        "decisions": decisions,
    }


def _iso_timestamp(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


def state_elapsed_seconds(record: dict, now: datetime | None = None) -> int:
    """Return seconds elapsed since the symbol entered its current timed state."""
    entered_at = record.get("state_entered_at")
    if not entered_at:
        return 0
    if now is None:
        now = datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    try:
        entered = datetime.fromisoformat(str(entered_at).replace("Z", "+00:00"))
    except ValueError:
        return 0
    if entered.tzinfo is None:
        entered = entered.replace(tzinfo=timezone.utc)
    return max(
        0,
        int(
            (
                now.astimezone(timezone.utc) - entered.astimezone(timezone.utc)
            ).total_seconds()
        ),
    )


def _transition_history(
    prior: dict, state: str, previous_state: str | None, entered_at: str | None
) -> list[dict]:
    """Return this session's compact state progression for a scanner card."""
    if state not in TRANSITION_HISTORY_STATES or not entered_at:
        return []
    if previous_state not in TRANSITION_HISTORY_STATES:
        return [{"state": state, "entered_at": entered_at}]

    history = [
        {"state": item.get("state"), "entered_at": item.get("entered_at")}
        for item in (prior.get("transition_history") or [])
        if item.get("state") in TRANSITION_HISTORY_STATES and item.get("entered_at")
    ]
    if not history:
        prior_entered_at = prior.get("state_entered_at")
        if previous_state and prior_entered_at:
            history = [{"state": previous_state, "entered_at": prior_entered_at}]

    if history and history[-1]["state"] == state:
        history[-1] = {"state": state, "entered_at": entered_at}
    else:
        history.append({"state": state, "entered_at": entered_at})
    return history[-MAX_TRANSITION_HISTORY:]


def _num(record: dict, key: str, default: float = 0.0) -> float:
    try:
        return float(record.get(key, default) or default)
    except (TypeError, ValueError):
        return default


def _tf_bull(record: dict, label: str) -> bool:
    tf = record.get("timeframes") or {}
    item = tf.get(label) or {}
    return bool(item.get("above_vwap") and item.get("supertrend"))


TREND_CONFIRMATION_ORDER = ("30s", "1m", "3m", "5m")


def _trend_confirmation_passed(record: dict, label: str) -> bool:
    if label == "30s":
        return bool(
            record.get("supertrend_30s_flip", record.get("supertrend_flip"))
            or record.get("supertrend_bullish")
        )
    return _tf_bull(record, label)


def sequential_trend_confirmation(
    record: dict,
    prior: dict | None = None,
    scan_time: datetime | None = None,
    log_events: bool = False,
) -> dict:
    """Evaluate SuperTrend confirmations as an ordered 30s→1m→3m→5m ladder."""
    prior = prior or {}
    if scan_time is None:
        scan_time = datetime.now(timezone.utc)
    if scan_time.tzinfo is None:
        scan_time = scan_time.replace(tzinfo=timezone.utc)
    scan_time_iso = _iso_timestamp(scan_time)

    prior_events = [
        dict(event)
        for event in (prior.get("trend_confirmation_events") or [])
        if (
            event.get("timeframe") in TREND_CONFIRMATION_ORDER
            and event.get("confirmed_at")
        )
    ]
    event_keys = {event.get("timeframe") for event in prior_events}
    ladder = []
    pending_started = False
    progression_count = 0
    conflicts = 0
    events = prior_events

    for label in TREND_CONFIRMATION_ORDER:
        confirmed = _trend_confirmation_passed(record, label)
        prior_confirmed = _trend_confirmation_passed(prior, label)
        if confirmed and not prior_confirmed and label not in event_keys:
            event = {
                "timeframe": label,
                "event": "confirmed",
                "confirmed_at": scan_time_iso,
            }
            events.append(event)
            event_keys.add(label)
            if log_events:
                logger.info(
                    "Sequential SuperTrend confirmation %s %s confirmed at %s",
                    record.get("symbol", ""),
                    label,
                    scan_time_iso,
                )
        if confirmed and not pending_started:
            state = "confirmed"
            progression_count += 1
        elif confirmed:
            state = "conflict"
            conflicts += 1
        else:
            state = "pending" if not pending_started else "missing"
            pending_started = True
        ladder.append({"timeframe": label, "confirmed": confirmed, "state": state})

    if conflicts:
        condition = "Weakening"
    elif progression_count >= 3:
        condition = "Stable"
    elif progression_count >= 1:
        condition = "Building"
    else:
        condition = "Weakening"

    return {
        "order": list(TREND_CONFIRMATION_ORDER),
        "ladder": ladder,
        "progression_count": progression_count,
        "conflict_count": conflicts,
        "condition": condition,
        "events": events[-16:],
    }


def _tf_detail(record: dict, label: str) -> dict:
    return (record.get("timeframes") or {}).get(label) or {}


def _tf_supportive(record: dict, label: str) -> bool:
    item = _tf_detail(record, label)
    return bool(
        item.get("supertrend")
        or item.get("near_supertrend_flip")
        or item.get("very_close_to_flipping")
    )


def _condition_crossed(current_passed: bool, prior_passed: bool) -> bool:
    return bool(current_passed and not prior_passed)


def _promotion_condition_changes(
    record: dict, prior: dict, scan_time: datetime | None = None
) -> list[str]:
    """Return positive scan-to-scan condition changes that explain a promotion."""
    changes: list[str] = []

    prior_vwap_relation = prior.get("vwap_relation")
    current_vwap_above = (
        record.get("vwap_relation") == "above" or _num(record, "vwap_distance_pct") >= 0
    )
    current_vwap_supportive = (
        record.get("vwap_relation") in {"testing", "above"}
        or _num(record, "vwap_distance_pct") >= 0
    )
    prior_vwap_supportive = (
        prior_vwap_relation in {"testing", "above"}
        or _num(prior, "vwap_distance_pct") >= 0
    )
    if current_vwap_above and prior_vwap_relation in {"below", "testing"}:
        changes.append("VWAP reclaim")
    elif _condition_crossed(current_vwap_supportive, prior_vwap_supportive):
        changes.append("VWAP support crossed")

    current_30s_flip = bool(
        record.get("supertrend_30s_flip", record.get("supertrend_flip"))
    )
    prior_30s_flip = bool(
        prior.get("supertrend_30s_flip", prior.get("supertrend_flip"))
    )
    if _condition_crossed(current_30s_flip, prior_30s_flip):
        changes.append("30s ST flip")
    elif _condition_crossed(
        bool(record.get("supertrend_flip")), bool(prior.get("supertrend_flip"))
    ):
        changes.append("30s ST flip")

    if _condition_crossed(
        bool(record.get("supertrend_bullish")),
        bool(prior.get("supertrend_bullish")),
    ):
        changes.append("SuperTrend supportive")

    for label in ("1m", "3m", "5m"):
        if _condition_crossed(
            _tf_supportive(record, label), _tf_supportive(prior, label)
        ):
            changes.append(f"{label} ST confirmation")
        elif _condition_crossed(_tf_bull(record, label), _tf_bull(prior, label)):
            changes.append(f"{label} VWAP/ST confirmation")

    session_gate = session_volume_diagnostics(record, scan_time)
    thresholds = [
        (
            "volume threshold crossed",
            "volume",
            session_gate["expected_minimum_volume"],
            0,
        ),
        (
            "dollar volume threshold crossed",
            "dollar_volume",
            session_gate["expected_minimum_dollar_volume"],
            0,
        ),
        (
            "RVOL threshold crossed",
            "rvol_proxy",
            session_gate["expected_minimum_rvol"],
            1,
        ),
        ("volume acceleration threshold crossed", "volume_acceleration", 1.2, 1),
        ("float turnover threshold crossed", "float_turnover_pct", 3, 0),
    ]
    for label, key, threshold, default in thresholds:
        if _condition_crossed(
            _num(record, key, default) >= threshold,
            _num(prior, key, default) >= threshold,
        ):
            changes.append(label)

    current_news = bool(
        record.get("headline")
        or "recent news" in set(record.get("discovery_reasons") or [])
    )
    prior_news = bool(
        prior.get("headline")
        or "recent news" in set(prior.get("discovery_reasons") or [])
    )
    if _condition_crossed(current_news, prior_news):
        changes.append("news catalyst appeared")

    return changes


def _market_session(now: datetime | None = None) -> str:
    if now is None:
        now = datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    market_time = now.astimezone(MARKET_TZ).time()
    if time(4, 0) <= market_time < time(9, 30):
        return "Pre-Market"
    if time(9, 30) <= market_time < time(10, 0):
        return "Open"
    if time(10, 0) <= market_time < time(15, 0):
        return "Midday"
    if time(15, 0) <= market_time < time(16, 0):
        return "Power Hour"
    return "After Hours"


def session_volume_diagnostics(record: dict, scan_time: datetime | None = None) -> dict:
    session = _market_session(scan_time)
    multiplier = SESSION_VOLUME_PROFILES[session]
    expected_volume = BASE_MIN_VOLUME * multiplier
    expected_dollar = BASE_MIN_DOLLAR_VOLUME * multiplier
    expected_rvol = BASE_MIN_RVOL * multiplier
    actual_volume = _num(record, "volume")
    actual_dollar = _num(record, "dollar_volume")
    actual_rvol = _num(record, "rvol_proxy", 1)
    volume_passed = actual_volume >= expected_volume
    dollar_passed = actual_dollar >= expected_dollar
    rvol_passed = actual_rvol >= expected_rvol
    return {
        "current_session": session,
        "expected_minimum_volume": round(expected_volume),
        "actual_volume": round(actual_volume),
        "volume_passed": volume_passed,
        "expected_minimum_dollar_volume": round(expected_dollar),
        "actual_dollar_volume": round(actual_dollar),
        "dollar_volume_passed": dollar_passed,
        "expected_minimum_rvol": round(expected_rvol, 2),
        "actual_rvol": round(actual_rvol, 2),
        "rvol_passed": rvol_passed,
        "passed": bool(volume_passed and dollar_passed and rvol_passed),
    }


def volume_pace_diagnostics(record: dict) -> dict:
    current_volume = _num(record, "volume")
    expected_volume = _num(record, "expected_volume_by_time")
    vpr = _num(
        record,
        "volume_pace_ratio",
        current_volume / expected_volume if expected_volume > 0 else 1,
    )
    five_minute_volume = _num(record, "five_minute_volume")
    expected_five_minute = _num(record, "expected_five_minute_volume")
    acceleration = _num(
        record,
        "acceleration_ratio",
        five_minute_volume / expected_five_minute if expected_five_minute > 0 else 1,
    )
    passed = bool(
        record.get(
            "volume_pace_passed",
            vpr >= VPI_MIN_PACE_RATIO and acceleration >= VPI_MIN_ACCELERATION_RATIO,
        )
    )
    return {
        "current_volume": round(current_volume),
        "expected_volume": round(expected_volume),
        "volume_pace_ratio": round(vpr, 2),
        "five_minute_volume": round(five_minute_volume),
        "expected_five_minute_volume": round(expected_five_minute),
        "acceleration_ratio": round(acceleration, 2),
        "passed": passed,
        "minimum_volume_pace_ratio": VPI_MIN_PACE_RATIO,
        "minimum_acceleration_ratio": VPI_MIN_ACCELERATION_RATIO,
    }


def _current_vwap_diagnostics(record: dict, prior: dict | None = None) -> dict:
    """Calculate the live VWAP gate inputs from the current bar-derived VWAP."""
    price = _num(record, "price")
    vwap = _num(record, "calculated_vwap", _num(record, "vwap_value"))
    distance = (
        (price - vwap) / vwap * 100.0
        if price and vwap
        else _num(record, "vwap_distance_pct")
    )
    prior_distance = None
    if prior:
        prior_price = _num(prior, "price")
        prior_vwap = _num(prior, "calculated_vwap", _num(prior, "vwap_value"))
        prior_distance = (
            (prior_price - prior_vwap) / prior_vwap * 100.0
            if prior_price and prior_vwap
            else _num(prior, "vwap_distance_pct")
        )
    fresh_reclaim = bool(prior_distance is not None and prior_distance < 0 <= distance)
    passed = bool(
        distance >= 0 or fresh_reclaim or distance >= -STRENGTHENING_VWAP_MAX_BELOW_PCT
    )
    return {
        "current_price": round(price, 6) if price else None,
        "calculated_vwap": round(vwap, 6) if vwap else None,
        "distance_pct": round(distance, 4),
        "bar_timeframe_source": record.get("vwap_bar_timeframe_source")
        or record.get("bar_timeframe_source")
        or "current intraday bars used for SuperTrend",
        "gate_passed": passed,
        "fresh_reclaim": fresh_reclaim,
        "max_below_tolerance_pct": STRENGTHENING_VWAP_MAX_BELOW_PCT,
    }


def _strengthening_vwap_qualified(record: dict, prior: dict | None = None) -> bool:
    """Return whether current VWAP structure allows Strengthening."""
    return bool(_current_vwap_diagnostics(record, prior).get("gate_passed"))


def _entry_ready_requirements(record: dict, prior: dict | None = None) -> bool:
    price_at_or_above_vwap = (
        _current_vwap_diagnostics(record, prior)["distance_pct"] >= 0
    )
    catalyst_30s = bool(
        record.get("supertrend_30s_flip", record.get("supertrend_flip"))
    )
    one_min_support = _tf_supportive(record, "1m") or bool(
        record.get("supertrend_bullish")
    )
    three_min_support = _tf_supportive(record, "3m")

    return all(
        [
            catalyst_30s,
            price_at_or_above_vwap,
            one_min_support,
            three_min_support,
        ]
    )


def _ratio_points(value: float, floor: float, ceiling: float, points: float) -> float:
    if value <= floor:
        return 0.0
    if ceiling <= floor:
        return points
    return max(0.0, min(points, ((value - floor) / (ceiling - floor)) * points))


def participation_surge_diagnostics(
    record: dict, prior: dict | None = None, scan_time: datetime | None = None
) -> dict:
    """Score the inactive→institutional-participation transition independent of news/gap/rank."""
    prior = prior or {}
    if scan_time is None:
        scan_time = datetime.now(timezone.utc)
    if scan_time.tzinfo is None:
        scan_time = scan_time.replace(tzinfo=timezone.utc)

    volume_ratios = {
        "1m": _num(
            record, "volume_acceleration_1m", _num(record, "volume_acceleration", 1)
        ),
        "3m": _num(
            record, "volume_acceleration_3m", _num(record, "volume_acceleration", 1)
        ),
        "5m": _num(
            record, "volume_acceleration_5m", _num(record, "acceleration_ratio", 1)
        ),
    }
    dollar_ratios = {
        "1m": _num(record, "dollar_flow_acceleration_1m", volume_ratios["1m"]),
        "3m": _num(record, "dollar_flow_acceleration_3m", volume_ratios["3m"]),
        "5m": _num(record, "dollar_flow_acceleration_5m", volume_ratios["5m"]),
    }
    best_volume = max(volume_ratios.values())
    sustained_volume = (volume_ratios["3m"] + volume_ratios["5m"]) / 2
    best_dollar = max(dollar_ratios.values())
    sustained_dollar = (dollar_ratios["3m"] + dollar_ratios["5m"]) / 2

    volume_points = _ratio_points(best_volume, 1.15, 5.0, 18) + _ratio_points(
        sustained_volume, 1.1, 3.5, 12
    )
    dollar_points = _ratio_points(best_dollar, 1.15, 5.0, 16) + _ratio_points(
        sustained_dollar, 1.1, 3.5, 12
    )

    vwap = _current_vwap_diagnostics(record, prior)
    distance = vwap["distance_pct"]
    if vwap["fresh_reclaim"]:
        vwap_points = 18
        vwap_state = "reclaiming VWAP"
    elif -0.35 <= distance <= 0.75:
        vwap_points = 18
        vwap_state = "at/near VWAP"
    elif -1.0 <= distance < -0.35 or 0.75 < distance <= 2.0:
        vwap_points = 11
        vwap_state = "VWAP supportive"
    elif distance > 2.0:
        vwap_points = max(0.0, 7 - (distance - 2.0) * 2.0)
        vwap_state = "extended above VWAP"
    else:
        vwap_points = 0.0
        vwap_state = "below VWAP"

    fresh_st = bool(record.get("supertrend_30s_flip", record.get("supertrend_flip")))
    prior_bullish = bool(prior.get("supertrend_bullish"))
    current_bullish = bool(record.get("supertrend_bullish"))
    if fresh_st:
        st_points = 16
        st_status = "fresh bullish flip"
    elif current_bullish and not prior_bullish:
        st_points = 12
        st_status = "new bullish support"
    elif current_bullish:
        st_points = 6
        st_status = "established bullish"
    else:
        st_points = 0
        st_status = "not bullish"

    quality = _num(record, "expansion_quality", 50)
    quality_points = max(0.0, min(16.0, quality / 100 * 16))

    quiet_before = (
        _num(prior, "volume_acceleration", 1) <= 1.25
        and _num(prior, "rvol_proxy", 1) <= 1.75
        and abs(_num(prior, "vwap_distance_pct")) <= 1.5
    )
    quiet_points = (
        8 if quiet_before else 3 if abs(_num(record, "pct_change")) <= 4 else 0
    )

    score = round(
        max(
            0.0,
            min(
                100.0,
                volume_points
                + dollar_points
                + vwap_points
                + st_points
                + quality_points
                + quiet_points,
            ),
        ),
        1,
    )
    major_conditions = {
        "volume_acceleration": sustained_volume >= 1.6 or best_volume >= 2.2,
        "dollar_flow_acceleration": sustained_dollar >= 1.6 or best_dollar >= 2.2,
        "vwap_proximity": vwap_points >= 11,
        "supertrend_transition": st_points >= 12,
        "expansion_quality": quality >= 58,
    }
    detected = bool(score >= 72 and all(major_conditions.values()))
    return {
        "timestamp": _iso_timestamp(scan_time),
        "vwap_distance_pct": round(distance, 4),
        "vwap_state": vwap_state,
        "st_status": st_status,
        "volume_acceleration": {k: round(v, 2) for k, v in volume_ratios.items()},
        "dollar_flow_acceleration": {k: round(v, 2) for k, v in dollar_ratios.items()},
        "current_dollar_flow": {
            "1m": round(_num(record, "current_dollar_flow_1m"), 2),
            "3m": round(_num(record, "current_dollar_flow_3m"), 2),
            "5m": round(_num(record, "current_dollar_flow_5m"), 2),
        },
        "baseline_dollar_flow_per_minute": round(
            _num(record, "baseline_dollar_flow_per_minute"), 2
        ),
        "expansion_quality": round(quality, 1),
        "participation_score": score,
        "current_phase": record.get("market_phase", "Emerging"),
        "major_conditions": major_conditions,
        "detected": detected,
        "alert": "Participation Surge Detected" if detected else "",
    }


def participation_gate_diagnostics(
    record: dict,
    prior: dict | None = None,
    scan_time: datetime | None = None,
    surge: dict | None = None,
) -> dict:
    """Hard prerequisite: buyers must be measurably entering before ranking."""
    prior = prior or {}
    surge = surge or participation_surge_diagnostics(record, prior, scan_time)
    pace = volume_pace_diagnostics(record)
    pace_acceleration = _num(record, "acceleration_ratio", 1)
    volume_1m = _num(
        record,
        "volume_acceleration_1m",
        _num(record, "volume_acceleration", pace_acceleration),
    )
    volume_3m = _num(
        record,
        "volume_acceleration_3m",
        _num(record, "volume_acceleration", pace_acceleration),
    )
    if pace["passed"]:
        volume_1m = max(volume_1m, pace_acceleration)
        volume_3m = max(volume_3m, pace_acceleration)
    dollar_1m = _num(record, "dollar_flow_acceleration_1m", volume_1m)
    dollar_3m = _num(record, "dollar_flow_acceleration_3m", volume_3m)
    dollar_5m = _num(
        record, "dollar_flow_acceleration_5m", _num(record, "acceleration_ratio", 1)
    )
    buying = _num(record, "green_volume_ratio", 1)
    if buying == 1 and pace["passed"]:
        buying = PARTICIPATION_MIN_BUYING_EXPANSION
    checks = [
        (
            "1-minute volume increasing",
            volume_1m,
            PARTICIPATION_MIN_ACCELERATION_RATIO,
            volume_1m >= PARTICIPATION_MIN_ACCELERATION_RATIO,
            "1-minute volume not increasing",
        ),
        (
            "3-minute volume increasing",
            volume_3m,
            PARTICIPATION_MIN_ACCELERATION_RATIO,
            volume_3m >= PARTICIPATION_MIN_ACCELERATION_RATIO,
            "3-minute volume not increasing",
        ),
        (
            "Dollar volume increasing",
            max(dollar_1m, dollar_3m, dollar_5m),
            PARTICIPATION_MIN_ACCELERATION_RATIO,
            max(dollar_1m, dollar_3m, dollar_5m)
            >= PARTICIPATION_MIN_ACCELERATION_RATIO,
            "Dollar flow not increasing",
        ),
        (
            "Participation acceleration above threshold",
            max(volume_1m, volume_3m, dollar_1m, dollar_3m, dollar_5m),
            PARTICIPATION_MIN_ACCELERATION_RATIO,
            max(volume_1m, volume_3m, dollar_1m, dollar_3m, dollar_5m)
            >= PARTICIPATION_MIN_ACCELERATION_RATIO,
            "No participation surge",
        ),
        (
            "Recent buying activity expanding",
            buying,
            PARTICIPATION_MIN_BUYING_EXPANSION,
            buying >= PARTICIPATION_MIN_BUYING_EXPANSION,
            "No buying expansion",
        ),
    ]
    failed = [
        failed for _label, _measured, _threshold, passed, failed in checks if not passed
    ]
    failed_criteria = [
        {
            "condition": label,
            "failed_reason": failed_reason,
            "measured": round(measured, 4),
            "threshold": round(threshold, 4),
        }
        for label, measured, threshold, passed, failed_reason in checks
        if not passed
    ]
    session = session_volume_diagnostics(record, scan_time)
    if not (session["volume_passed"] or pace["passed"]):
        failed.append("Volume below threshold")
        failed_criteria.append(
            {
                "condition": "Session volume",
                "failed_reason": "Volume below threshold",
                "measured": session["actual_volume"],
                "threshold": session["expected_minimum_volume"],
            }
        )
    if not (
        session["dollar_volume_passed"]
        or _num(record, "dollar_volume")
        >= session["expected_minimum_dollar_volume"] * 0.5
    ):
        failed.append("Dollar volume below threshold")
        failed_criteria.append(
            {
                "condition": "Session dollar volume",
                "failed_reason": "Dollar volume below threshold",
                "measured": session["actual_dollar_volume"],
                "threshold": round(session["expected_minimum_dollar_volume"] * 0.5),
            }
        )
    if not (
        session["rvol_passed"]
        or pace["passed"]
        or _num(record, "rvol_proxy", 1) >= BASE_MIN_RVOL
    ):
        failed.append("RVOL below threshold")
        failed_criteria.append(
            {
                "condition": "RVOL",
                "failed_reason": "RVOL below threshold",
                "measured": round(_num(record, "rvol_proxy", 1), 4),
                "threshold": BASE_MIN_RVOL,
            }
        )
    return {
        "passed": not failed,
        "status": "PASS" if not failed else "FAIL",
        "reason": "Participation Present" if not failed else "No Participation",
        "failed_reasons": list(dict.fromkeys(failed)),
        "checks": [
            {
                "condition": label,
                "passed": passed,
                "failed_reason": failed_reason,
                "measured": round(measured, 4),
                "threshold": round(threshold, 4),
            }
            for label, measured, threshold, passed, failed_reason in checks
        ],
        "failed_criteria": failed_criteria,
        "minimum_acceleration_ratio": PARTICIPATION_MIN_ACCELERATION_RATIO,
    }


def participation_gate_rejection_diagnostics(records: list[dict]) -> dict:
    """Summarize hard-gate participation rejections for scan-level diagnostics."""
    rejected = [
        record
        for record in records
        if record.get("qualified_for_ranking") is False
        and (record.get("participation_gate") or {}).get("status") == "FAIL"
    ]
    by_reason: dict[str, int] = {}
    details = []
    for record in rejected:
        gate = record.get("participation_gate") or {}
        failed_reasons = gate.get("failed_reasons") or []
        for reason in failed_reasons:
            by_reason[reason] = by_reason.get(reason, 0) + 1
        details.append(
            {
                "symbol": record.get("symbol", ""),
                "candidate_status": record.get("candidate_status")
                or record.get("status", ""),
                "failed_reasons": failed_reasons,
                "failed_criteria": gate.get("failed_criteria") or [],
            }
        )
    return {
        "candidates_rejected": len(rejected),
        "rejected_by_reason": by_reason,
        "details": details,
    }


def structure_gate_diagnostics(record: dict, prior: dict | None = None) -> dict:
    """Require technical structure only after participation is present."""
    vwap = _current_vwap_diagnostics(record, prior)
    distance = vwap["distance_pct"]
    trend = sequential_trend_confirmation(record, prior)
    checks = [
        ("Near VWAP", -1.0 <= distance <= 2.5, "Not near VWAP"),
        (
            "Fresh or sequential SuperTrend confirmation",
            bool(
                record.get("supertrend_flip")
                or record.get("supertrend_30s_flip")
                or trend["progression_count"] >= 2
                or record.get("supertrend_bullish")
            ),
            "SuperTrend not confirmed",
        ),
        ("Not materially extended", distance <= 2.5, "Materially extended"),
        (
            "Healthy price structure",
            bool(
                record.get("higher_lows")
                or record.get("near_hod")
                or _num(record, "expansion_quality", 50) >= 55
            ),
            "Price structure not healthy",
        ),
    ]
    failed = [failed for _label, passed, failed in checks if not passed]
    return {
        "passed": not failed,
        "status": "PASS" if not failed else "FAIL",
        "reason": "Structure Ready" if not failed else "Structure Not Ready",
        "failed_reasons": failed,
        "checks": [
            {"condition": label, "passed": passed, "failed_reason": failed_reason}
            for label, passed, failed_reason in checks
        ],
    }


def _quality_band(score: float) -> str:
    if score >= 90:
        return "Exceptional"
    if score >= 75:
        return "Strong"
    if score >= 55:
        return "Acceptable"
    if score >= 30:
        return "Weak"
    return "Poor"


def momentum_quality_diagnostics(
    record: dict, prior: dict | None = None, scan_time: datetime | None = None
) -> dict:
    """Score how orderly and sustainable the current momentum move is.

    Participation Surge asks whether meaningful participation began; this
    diagnostic asks whether the resulting move is being absorbed cleanly.
    """
    prior = prior or {}
    if scan_time is None:
        scan_time = datetime.now(timezone.utc)
    if scan_time.tzinfo is None:
        scan_time = scan_time.replace(tzinfo=timezone.utc)

    distance = _current_vwap_diagnostics(record, prior)["distance_pct"]
    abs_distance = abs(distance)
    if record.get("vwap_relation") == "above" or distance >= 0:
        vwap_respect = 92 - max(0.0, abs_distance - 0.75) * 9
        vwap_note = "riding VWAP" if distance <= 2.0 else "extended above VWAP"
    elif distance >= -0.65 or record.get("vwap_relation") == "testing":
        vwap_respect = 74 - max(0.0, abs_distance - 0.35) * 10
        vwap_note = "VWAP pullback holding"
    else:
        vwap_respect = 42 - min(32.0, (abs_distance - 1.0) * 8)
        vwap_note = "VWAP failures / wide oscillation"
    if prior.get("vwap_relation") == "below" and distance >= 0:
        vwap_respect += 8
        vwap_note = "quick VWAP reclaim"

    trend_sequence = sequential_trend_confirmation(record, prior, scan_time)
    progression = trend_sequence["progression_count"]
    conflicts = trend_sequence["conflict_count"]
    if progression >= 4:
        st_integrity = 94
        st_note = "full sequential ST support"
    elif progression == 3:
        st_integrity = 82
        st_note = "multi-timeframe ST support"
    elif progression == 2:
        st_integrity = 68
        st_note = "early ST confirmation"
    elif record.get("supertrend_bullish"):
        st_integrity = 56
        st_note = "single-frame ST support"
    else:
        st_integrity = 28
        st_note = "trend structure not green"
    if record.get("supertrend_30s_flip", record.get("supertrend_flip")):
        st_integrity += 6
    st_integrity -= conflicts * 18
    if prior.get("supertrend_bullish") and not record.get("supertrend_bullish"):
        st_integrity -= 22
        st_note = "recent ST break"

    expansion_quality = _num(record, "expansion_quality", 50)
    structure = 0.55 * expansion_quality
    structure += 14 if record.get("higher_lows") else -10
    structure += 9 if record.get("near_hod") else -6
    if _num(record, "pct_change") < -1:
        structure -= 12
    structure_note = (
        "orderly higher-low expansion"
        if record.get("higher_lows")
        else "overlapping / reversal-prone candles"
    )

    volume_ratios = [
        _num(record, "volume_acceleration_1m", _num(record, "volume_acceleration", 1)),
        _num(record, "volume_acceleration_3m", _num(record, "volume_acceleration", 1)),
        _num(record, "volume_acceleration_5m", _num(record, "acceleration_ratio", 1)),
    ]
    sustained = (volume_ratios[1] + volume_ratios[2]) / 2
    one_bar_spike = volume_ratios[0] > max(2.5, sustained * 1.9)
    green_ratio = _num(record, "green_volume_ratio", 1)
    participation = 46 + min(28.0, max(0.0, sustained - 1.0) * 16)
    participation += min(16.0, max(0.0, green_ratio - 1.0) * 12)
    if one_bar_spike:
        participation -= 28
    participation_note = (
        "sustained buying pressure"
        if not one_bar_spike and sustained >= 1.4
        else "one-bar spike / fading participation"
    )

    pct_change = abs(_num(record, "pct_change"))
    churn_penalty = max(0.0, max(volume_ratios) - sustained) * 9
    extension_penalty = max(0.0, abs_distance - 3.0) * 5
    efficiency = 42 + min(35.0, pct_change * 1.4) + (expansion_quality - 50) * 0.35
    efficiency -= churn_penalty + extension_penalty
    if record.get("near_hod") and distance >= -0.5:
        efficiency += 8
    efficiency_note = (
        "directional progress per participation"
        if efficiency >= 60
        else "chaotic volatility versus net progress"
    )

    factors = {
        "vwap_respect": round(max(0.0, min(100.0, vwap_respect)), 1),
        "st_integrity": round(max(0.0, min(100.0, st_integrity)), 1),
        "structure": round(max(0.0, min(100.0, structure)), 1),
        "participation": round(max(0.0, min(100.0, participation)), 1),
        "efficiency": round(max(0.0, min(100.0, efficiency)), 1),
    }
    score = round(
        factors["vwap_respect"] * 0.22
        + factors["st_integrity"] * 0.22
        + factors["structure"] * 0.22
        + factors["participation"] * 0.18
        + factors["efficiency"] * 0.16,
        1,
    )
    return {
        "timestamp": _iso_timestamp(scan_time),
        "score": score,
        "band": _quality_band(score),
        "factors": factors,
        "factor_notes": {
            "vwap_respect": vwap_note,
            "st_integrity": st_note,
            "structure": structure_note,
            "participation": participation_note,
            "efficiency": efficiency_note,
        },
    }


def trend_stability_diagnostics(
    record: dict, prior: dict | None = None, scan_time: datetime | None = None
) -> dict:
    """Score whether an existing trend is strengthening, stable, or deteriorating.

    Momentum Quality measures the cleanliness of the current move; Trend Stability
    adds time-aware structure checks so equally strong momentum candidates can be
    separated by VWAP durability, SuperTrend continuity, pullback control, and
    follow-through after consolidations.
    """
    prior = prior or {}
    if scan_time is None:
        scan_time = datetime.now(timezone.utc)
    if scan_time.tzinfo is None:
        scan_time = scan_time.replace(tzinfo=timezone.utc)

    current_vwap = _current_vwap_diagnostics(record, prior)
    distance = current_vwap["distance_pct"]
    prior_distance = _num(prior, "vwap_distance_pct", distance)
    explicit_slope = record.get("vwap_slope_pct", record.get("vwap_slope"))
    vwap_slope = (
        _num(record, "vwap_slope_pct", _num(record, "vwap_slope"))
        if explicit_slope is not None
        else distance - prior_distance
    )
    vwap_violations = _num(
        record, "vwap_violation_count", _num(record, "vwap_deep_violation_count")
    )
    vwap_crosses = _num(record, "vwap_cross_count")
    vwap_stability = 68 + min(18.0, max(0.0, vwap_slope) * 16)
    if record.get("vwap_relation") == "above" and distance >= -0.15:
        vwap_stability += 14
    elif record.get("vwap_relation") == "testing" or distance >= -0.65:
        vwap_stability += 5
    else:
        vwap_stability -= min(34.0, abs(distance) * 8)
    vwap_stability -= min(28.0, vwap_violations * 9 + vwap_crosses * 5)
    if vwap_slope < -0.05:
        vwap_stability -= min(18.0, abs(vwap_slope) * 20)
    vwap_note = (
        "positive VWAP slope / respect"
        if vwap_stability >= 75
        else (
            "VWAP flattening or repeated tests"
            if vwap_stability >= 50
            else "VWAP failures / oscillation"
        )
    )

    trend_sequence = sequential_trend_confirmation(record, prior, scan_time)
    progression = trend_sequence["progression_count"]
    conflicts = trend_sequence["conflict_count"]
    st_flips = _num(record, "supertrend_flip_count", _num(record, "st_flip_count"))
    prior_st = bool(prior.get("supertrend_bullish"))
    current_st = bool(record.get("supertrend_bullish"))
    st_stability = 34 + progression * 14
    if current_st:
        st_stability += 14
    if current_st and prior_st:
        st_stability += 8
    if (
        record.get("supertrend_30s_flip", record.get("supertrend_flip"))
        and not prior_st
    ):
        st_stability += 4
    st_stability -= conflicts * 16 + max(0.0, st_flips - 1) * 12
    if prior_st and not current_st:
        st_stability -= 28
    st_note = (
        "bullish SuperTrend support intact"
        if st_stability >= 75
        else (
            "SuperTrend support is mixed"
            if st_stability >= 50
            else "SuperTrend structure deteriorating"
        )
    )

    pullback_depth = abs(_num(record, "pullback_depth_pct", max(0.0, -distance)))
    retracement = abs(_num(record, "retracement_pct", pullback_depth))
    lower_lows = bool(record.get("lower_lows")) or (
        prior.get("higher_lows") and not record.get("higher_lows")
    )
    panic = bool(record.get("panic_candle") or record.get("panic_candles"))
    pullback_quality = 64 + (18 if record.get("higher_lows") else -8)
    pullback_quality += 7 if record.get("vwap_relation") in {"above", "testing"} else -8
    pullback_quality -= min(32.0, max(pullback_depth, retracement) * 7)
    if lower_lows:
        pullback_quality -= 18
    if panic:
        pullback_quality -= 22
    pullback_note = (
        "controlled higher-low pullbacks"
        if pullback_quality >= 75
        else (
            "pullbacks need monitoring"
            if pullback_quality >= 50
            else "deep/lower-low pullbacks"
        )
    )

    expansion_quality = _num(record, "expansion_quality", 50)
    rejection_count = _num(
        record, "new_high_rejection_count", _num(record, "rejection_count")
    )
    made_fresh_high = bool(record.get("fresh_higher_high", record.get("near_hod")))
    follow_through = _num(
        record, "follow_through_pct", max(0.0, _num(record, "pct_change"))
    )
    continuation_strength = 48 + expansion_quality * 0.34
    continuation_strength += 13 if made_fresh_high else -7
    continuation_strength += min(12.0, follow_through * 0.55)
    continuation_strength -= min(30.0, rejection_count * 10)
    if _num(record, "volume_acceleration", 1) < 0.85:
        continuation_strength -= 10
    continuation_note = (
        "fresh highs followed by orderly rest"
        if continuation_strength >= 75
        else (
            "limited follow-through"
            if continuation_strength >= 50
            else "new highs being rejected"
        )
    )

    factors = {
        "vwap_stability": round(max(0.0, min(100.0, vwap_stability)), 1),
        "st_stability": round(max(0.0, min(100.0, st_stability)), 1),
        "pullback_quality": round(max(0.0, min(100.0, pullback_quality)), 1),
        "continuation_strength": round(max(0.0, min(100.0, continuation_strength)), 1),
    }
    score = round(
        factors["vwap_stability"] * 0.28
        + factors["st_stability"] * 0.26
        + factors["pullback_quality"] * 0.23
        + factors["continuation_strength"] * 0.23,
        1,
    )
    return {
        "timestamp": _iso_timestamp(scan_time),
        "score": score,
        "band": _quality_band(score),
        "factors": factors,
        "factor_notes": {
            "vwap_stability": vwap_note,
            "st_stability": st_note,
            "pullback_quality": pullback_note,
            "continuation_strength": continuation_note,
        },
    }


def momentum_evidence(
    record: dict, prior: dict | None = None, scan_time: datetime | None = None
) -> tuple[float, list[str], list[str]]:
    """Score developing momentum without requiring a completed setup."""
    prior = prior or {}
    reasons: list[str] = []
    cautions: list[str] = []
    points = 0.0

    discovery = set(record.get("discovery_reasons") or [])
    if record.get("headline"):
        points += 12
        reasons.append("recent news catalyst")
    elif "recent news" in discovery:
        points += 7
        reasons.append("news-driven discovery")

    vol = _num(record, "volume")
    dollar = _num(record, "dollar_volume")
    rvol = _num(record, "rvol_proxy", 1)
    accel = _num(record, "volume_acceleration", 1)
    vpi = volume_pace_diagnostics(record)
    vpr = vpi["volume_pace_ratio"]
    acceleration_ratio = vpi["acceleration_ratio"]
    turnover = _num(record, "float_turnover_pct")
    volume_gate = session_volume_diagnostics(record, scan_time)
    expected_vol = volume_gate["expected_minimum_volume"]
    expected_dollar = volume_gate["expected_minimum_dollar_volume"]
    expected_rvol = volume_gate["expected_minimum_rvol"]

    if vpi["passed"]:
        points += min(24, 8 + (vpr - 1.0) * 7 + (acceleration_ratio - 1.0) * 5)
        reasons.append(
            f"VPI {vpr:.1f}× pace / {acceleration_ratio:.1f}× 5m acceleration"
        )
    elif vpr >= 1.2:
        points += min(12, 4 + (vpr - 1.0) * 5)
        reasons.append(f"VPI {vpr:.1f}× participation pace")
    elif vpr < 0.8:
        points -= 8
        cautions.append("below normal volume pace")

    if volume_gate["volume_passed"]:
        points += min(10, 4 + vol / max(expected_vol * 6, 1))
        reasons.append(f"{volume_gate['current_session']} feed volume qualified")
    if volume_gate["dollar_volume_passed"]:
        points += min(8, 3 + dollar / max(expected_dollar * 8, 1))
        reasons.append(f"{volume_gate['current_session']} dollar volume qualified")
    if volume_gate["rvol_passed"]:
        points += min(10, 4 + (rvol - expected_rvol) * 1.8)
        reasons.append(f"{volume_gate['current_session']} RVOL {rvol:.1f}×")
    if accel >= 1.2:
        points += min(18, 7 + (accel - 1.0) * 10)
        reasons.append(f"accelerating volume {accel:.1f}×")
    elif not volume_gate["passed"] and rvol < max(1.2, expected_rvol * 0.8):
        points -= 15
        cautions.append("inactive volume")
    if turnover >= 3:
        points += min(6, turnover * 0.75)
        reasons.append(f"float turnover {turnover:.1f}%")

    surge = participation_surge_diagnostics(record, prior, scan_time)
    quality = momentum_quality_diagnostics(record, prior, scan_time)
    if surge["participation_score"] >= 55:
        points += min(22, (surge["participation_score"] - 45) * 0.55)
        reasons.append(f"Participation Surge {surge['participation_score']:.0f}/100")
    if surge["detected"]:
        points += 10
        reasons.append("Participation Surge Detected")

    quality_score = quality["score"]
    points += (quality_score - 50) * 0.22
    if quality_score >= 75:
        reasons.append(
            f"Momentum Quality {quality_score:.0f}/100 {quality['band'].lower()}"
        )
    elif quality_score < 40:
        cautions.append(f"weak Momentum Quality {quality_score:.0f}/100")

    if abs(_num(record, "pct_change")) <= 4 and accel >= 1.2:
        points += 6
        reasons.append("flat base with activity expanding")

    was_below = prior.get("vwap_relation") == "below"
    vwap_relation = record.get("vwap_relation")
    if vwap_relation == "above":
        points += 18
        reasons.append("VWAP improving" if was_below else "above VWAP")
    elif vwap_relation == "testing":
        points += 14
        reasons.append("VWAP improving" if was_below else "near VWAP")
    else:
        distance = _num(record, "vwap_distance_pct")
        if distance >= 0:
            points += 18
            reasons.append("above VWAP")
        elif distance >= -1.0:
            points += 8
            reasons.append("near VWAP")
        else:
            points -= min(24, 12 + abs(distance) * 3)
            cautions.append("poor VWAP relationship")
    if was_below and (
        vwap_relation == "above" or _num(record, "vwap_distance_pct") >= 0
    ):
        points += 16
        reasons.append("VWAP reclaim")

    current_30s_flip = bool(
        record.get("supertrend_30s_flip", record.get("supertrend_flip"))
    )
    if current_30s_flip:
        points += 22
        reasons.append("30-second SuperTrend flip")
    elif record.get("supertrend_bullish"):
        points += 8
        reasons.append("SuperTrend supportive")

    trend_sequence = sequential_trend_confirmation(record, prior, scan_time)
    progression_points = {2: 12, 3: 23, 4: 26}
    if trend_sequence["progression_count"] >= 2:
        points += progression_points.get(trend_sequence["progression_count"], 0)
        reasons.append(
            f"Sequential ST {trend_sequence['progression_count']}/4 {trend_sequence['condition'].lower()}"
        )
    elif trend_sequence["progression_count"] == 1:
        reasons.append("30s ST candidate awaiting 1m confirmation")
    if trend_sequence["conflict_count"]:
        points -= min(24, trend_sequence["conflict_count"] * 12)
        cautions.append("conflicting SuperTrend timeframe order")

    if record.get("higher_lows"):
        points += 5
        reasons.append("higher lows")
    if record.get("ema65_relation") == "above":
        points += 3
        reasons.append("above EMA65")

    if prior:
        if vol > _num(prior, "volume") * 1.05:
            points += 7
            reasons.append("feed volume increased since prior scan")
        if dollar > _num(prior, "dollar_volume") * 1.05:
            points += 7
            reasons.append("dollar flow increased since prior scan")
        if vpr > _num(prior, "volume_pace_ratio", 1) + 0.25:
            points += 8
            reasons.append("VPI improved since prior scan")
        if rvol > _num(prior, "rvol_proxy", 1) + 0.25:
            points += 6
            reasons.append("RVOL improved since prior scan")
        if _num(record, "opportunity_score") > _num(prior, "opportunity_score") + 3:
            points += 2
            reasons.append("momentum score improving")

    if _num(record, "spread_pct") > 6:
        points -= 20
        cautions.append("wide spread")
    if record.get("risk_flags"):
        points -= min(25, len(record.get("risk_flags") or []) * 8)
        cautions.append("headline risk flags present")

    return max(0.0, min(100.0, points)), reasons[:12], cautions[:6]


def _supertrend_state(record: dict, label: str) -> str:
    if label == "30s":
        if record.get("supertrend_30s_flip", record.get("supertrend_flip")):
            return "flipped green"
        if record.get("supertrend_bullish"):
            return "green"
        return "not green"
    detail = _tf_detail(record, label)
    if detail.get("supertrend"):
        return "green"
    if detail.get("near_supertrend_flip") or detail.get("very_close_to_flipping"):
        return "near flip"
    return "not green"


def _strengthening_promotion_diagnostic(record: dict, score: float) -> dict:
    return {
        "vwap_relationship": record.get("vwap_relation"),
        "supertrend_30s_state": _supertrend_state(record, "30s"),
        "supertrend_1m_state": _supertrend_state(record, "1m"),
        "supertrend_3m_state": _supertrend_state(record, "3m"),
        "volume_acceleration": round(_num(record, "volume_acceleration", 1), 2),
        "final_weighted_score": round(score, 1),
    }


def classify_state(
    record: dict, prior: dict | None = None, scan_time: datetime | None = None
) -> str:
    score, reasons, cautions = momentum_evidence(record, prior, scan_time)
    prior_state = (prior or {}).get("candidate_status") or (prior or {}).get("status")
    if _num(record, "dollar_volume") < 50_000 or _num(record, "spread_pct") > 10:
        return "Removed"
    if _entry_ready_requirements(record, prior):
        return "Entry Ready"
    if (
        prior
        and score
        < _num(prior, "scanner_v2_score", _num(prior, "opportunity_score")) - 12
    ):
        return "Weakening"
    if score >= 66 and _strengthening_vwap_qualified(record, prior):
        return "Strengthening"
    if score >= 52:
        return "Emerging"
    if (
        score >= 34
        or record.get("headline")
        or session_volume_diagnostics(record, scan_time)["rvol_passed"]
    ):
        return "Watching"
    return "New" if not prior_state else "Removed"


def apply_scanner_v2(
    records: list[dict],
    previous_by_symbol: dict[str, dict],
    scan_time: datetime | None = None,
) -> list[dict]:
    output = []
    if scan_time is None:
        scan_time = datetime.now(timezone.utc)
    if scan_time.tzinfo is None:
        scan_time = scan_time.replace(tzinfo=timezone.utc)
    scan_time_iso = _iso_timestamp(scan_time)
    for source in records:
        record = dict(source)
        prior = previous_by_symbol.get(record.get("symbol"), {})
        previous_state = prior.get("candidate_status") or prior.get("status")
        vwap_gate_diagnostics = _current_vwap_diagnostics(record, prior)
        volume_session_diagnostics = session_volume_diagnostics(record, scan_time)
        volume_pace = volume_pace_diagnostics(record)
        trend_sequence = sequential_trend_confirmation(
            record, prior, scan_time, log_events=True
        )
        phase_update = apply_market_phase(record, prior, scan_time)
        record.update(phase_update)
        surge = participation_surge_diagnostics(record, prior, scan_time)
        participation_gate = participation_gate_diagnostics(
            record, prior, scan_time, surge
        )
        structure_gate = structure_gate_diagnostics(record, prior)
        gates_passed = participation_gate["passed"]
        qualified_for_ranking = (
            participation_gate["passed"] and structure_gate["passed"]
        )
        if not participation_gate["passed"]:
            score, reasons, cautions = 0.0, [], participation_gate["failed_reasons"]
            state = "Rejected – No Participation"
        else:
            score, reasons, cautions = momentum_evidence(record, prior, scan_time)
            state = classify_state(record, prior, scan_time)
        advanced = STATE_RANK.get(state, 0) > STATE_RANK.get(previous_state, 0)
        entered_watch = state in WATCH_STATES and previous_state not in WATCH_STATES
        prior_entered_at = prior.get("state_entered_at")
        if (
            state in TRANSITION_HISTORY_STATES
            and state == previous_state
            and prior_entered_at
        ):
            state_entered_at = prior_entered_at
        elif state in TRANSITION_HISTORY_STATES:
            state_entered_at = scan_time_iso
        else:
            state_entered_at = None
        state_elapsed = state_elapsed_seconds(
            {"state_entered_at": state_entered_at}, scan_time
        )
        transition_history = _transition_history(
            prior, state, previous_state, state_entered_at
        )
        promotion_changes = (
            _promotion_condition_changes(record, prior, scan_time)
            if advanced and state in PROMOTION_TARGET_STATES
            else []
        )
        strengthening_promotion_diagnostic = (
            _strengthening_promotion_diagnostic(record, score)
            if advanced and state == "Strengthening"
            else None
        )
        if strengthening_promotion_diagnostic:
            logger.info(
                "Strengthening promotion %s: VWAP=%s, 30s ST=%s, 1m ST=%s, 3m ST=%s, volume acceleration=%s, final weighted score=%s",
                record.get("symbol", ""),
                strengthening_promotion_diagnostic["vwap_relationship"],
                strengthening_promotion_diagnostic["supertrend_30s_state"],
                strengthening_promotion_diagnostic["supertrend_1m_state"],
                strengthening_promotion_diagnostic["supertrend_3m_state"],
                strengthening_promotion_diagnostic["volume_acceleration"],
                strengthening_promotion_diagnostic["final_weighted_score"],
            )
        quality = momentum_quality_diagnostics(record, prior, scan_time)
        stability = trend_stability_diagnostics(record, prior, scan_time)
        quality_adjustment = (quality["score"] - 50) * 0.18
        stability_adjustment = (stability["score"] - 50) * 0.10
        current_momentum = round(
            max(
                0.0,
                min(
                    100.0,
                    (
                        (
                            score
                            + max(0.0, surge["participation_score"] - 65) * 0.14
                            + quality_adjustment
                            + stability_adjustment
                        )
                        if gates_passed
                        else 0.0
                    ),
                ),
            ),
            1,
        )
        record.update(
            {
                "scanner_version": "V2",
                "scanner_v2_score": current_momentum,
                "current_momentum": current_momentum,
                "candidate_status": state,
                "decision_status": state,
                "qualified_for_ranking": qualified_for_ranking,
                "participation_gate": participation_gate,
                "structure_gate": structure_gate,
                "rejection_reason": (
                    None
                    if participation_gate["passed"]
                    else participation_gate["reason"]
                ),
                "action": (
                    "Evaluate for entry"
                    if qualified_for_ranking
                    else (
                        "Ignore"
                        if not participation_gate["passed"]
                        else "Waiting for structure"
                    )
                ),
                "previous_candidate_status": previous_state or "None",
                "advanced_state": advanced,
                "entered_watchlist": entered_watch,
                "alert_event": bool(entered_watch or advanced),
                "promotion_condition_changes": promotion_changes,
                "promotion_trigger": (
                    promotion_changes[0] if promotion_changes else None
                ),
                "strengthening_promotion_diagnostic": strengthening_promotion_diagnostic,
                "strengthening_vwap_gate": vwap_gate_diagnostics,
                "volume_session_diagnostics": volume_session_diagnostics,
                "volume_pace_diagnostics": volume_pace,
                "volume_pace_passed": volume_pace["passed"],
                "trend_confirmation_sequence": trend_sequence,
                "trend_ladder": trend_sequence["ladder"],
                "trend_condition": trend_sequence["condition"],
                "trend_confirmation_events": trend_sequence["events"],
                "vwap_distance_pct": vwap_gate_diagnostics["distance_pct"],
                "status": state,
                "state_entered_at": state_entered_at,
                "state_elapsed_seconds": state_elapsed,
                "transition_history": transition_history,
                "participation_surge_score": surge["participation_score"],
                "participation_surge_detected": surge["detected"],
                "participation_surge_alert": surge["alert"],
                "participation_surge_diagnostics": surge,
                "momentum_quality": quality["score"],
                "momentum_quality_score": quality["score"],
                "momentum_quality_band": quality["band"],
                "momentum_quality_diagnostics": quality,
                "trend_stability": stability["score"],
                "trend_stability_score": stability["score"],
                "trend_stability_band": stability["band"],
                "trend_stability_diagnostics": stability,
                "alert_event": bool(entered_watch or advanced or surge["detected"]),
                "reasons": reasons or record.get("reasons", []),
                "cautions": list(
                    dict.fromkeys((record.get("cautions") or []) + cautions)
                ),
            }
        )
        record["trigger_diagnostics"] = trigger_diagnostics(record, prior, scan_time)
        record["trigger"] = record["trigger_diagnostics"]["trigger"]
        record["trigger_reasons"] = record["trigger_diagnostics"]["reasons"]
        record["strengthening_decision"] = strengthening_decision(record, scan_time)
        output.append(record)
    return sorted(output, key=_ranked_record_sort_key, reverse=True)

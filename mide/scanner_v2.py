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

    for label, text, pts in [
        ("1m", "1-minute confirmation", 12),
        ("3m", "3-minute confirmation", 11),
        ("5m", "5-minute confirmation", 3),
    ]:
        if _tf_bull(record, label):
            points += pts
            reasons.append(text)

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
        score, reasons, cautions = momentum_evidence(record, prior, scan_time)
        state = classify_state(record, prior, scan_time)
        previous_state = prior.get("candidate_status") or prior.get("status")
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
        vwap_gate_diagnostics = _current_vwap_diagnostics(record, prior)
        volume_session_diagnostics = session_volume_diagnostics(record, scan_time)
        volume_pace = volume_pace_diagnostics(record)
        phase_update = apply_market_phase(record, prior, scan_time)
        current_momentum = round(score, 1)
        record.update(
            {
                "scanner_version": "V2",
                "scanner_v2_score": current_momentum,
                "current_momentum": current_momentum,
                "candidate_status": state,
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
                "vwap_distance_pct": vwap_gate_diagnostics["distance_pct"],
                "status": state,
                "state_entered_at": state_entered_at,
                "state_elapsed_seconds": state_elapsed,
                "transition_history": transition_history,
                **phase_update,
                "reasons": reasons or record.get("reasons", []),
                "cautions": list(
                    dict.fromkeys((record.get("cautions") or []) + cautions)
                ),
            }
        )
        record["strengthening_decision"] = strengthening_decision(record, scan_time)
        output.append(record)
    return sorted(output, key=_ranked_record_sort_key, reverse=True)

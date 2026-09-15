"""GS455: admit early ignition and elevate fresh 3m ST/VWAP confirmation.

Live validation on 2026-09-15 exposed two adjacent operator-timing gaps on RETO.
Webull surfaced RETO as a native five-minute mover near 09:34 ET while it was only
about +2.6% with roughly 19k shares traded. Walter's broad 3% OR 100k-share
prefilter therefore discarded it just before the move matured. Later, Walter's
already-computed deterministic 3-minute SuperTrend-line/VWAP-line cross occurred
before a large continuation, but that event remained secondary recorder evidence
instead of receiving an operator-attention pulse.

GS455 makes two deliberately narrow changes:

* During only the first 15 regular-session minutes, a native-Webull-universe symbol
  may pass the cheap prefilter at >=2% AND >=15,000 shares. The ordinary 3% OR
  100,000-share contract resumes at 09:45 ET. Price/float/participation/structure,
  anti-chase, readiness, and execution gates are unchanged.
* A fresh deterministic GS378 3m ST/VWAP cross becomes high-priority maturation
  evidence when the current 1m and 3m structures are both constructive and there
  is already supporting market participation/flow. Near VWAP it may raise a
  presentation state to LOOK NOW. If price is already >5% extended, CHASE / WAIT
  remains authoritative, but Walter still emits one distinct LOOK NOW attention
  alert describing the confirmation and explicitly says DO NOT CHASE.

No new market-data request or indicator calculation is introduced. GS378 remains
canonical for crossover truth and all entry/alert qualification fields remain
untouched.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import time
from functools import wraps
from typing import Any


EARLY_OPEN_START = time(9, 30)
EARLY_OPEN_END = time(9, 45)
EARLY_OPEN_MIN_PCT_CHANGE = 2.0
EARLY_OPEN_MIN_VOLUME = 15_000.0
THREE_MINUTE_NEW_SECONDS = 150.0
LOOK_NOW_MAX_VWAP_DISTANCE_PCT = 5.0

_PREFILTER_FAILURE = "Percent change and average volume below thresholds"
_CONFIRMATION_PROVENANCE = "FRESH_3M_ST_VWAP_CONFIRMATION"


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


def _market_now():
    from .time_service import eastern_time

    return eastern_time()


def _inside_early_open_window() -> bool:
    now = _market_now()
    current = now.time().replace(tzinfo=None)
    return EARLY_OPEN_START <= current < EARLY_OPEN_END


def _early_open_prefilter_decision(original, symbol: str, snapshot: dict, settings) -> dict:
    """Apply one bounded early-open discovery exception to the existing decision."""
    base = original(symbol, snapshot, settings)
    if base.get("passed") or not _inside_early_open_window():
        return base
    if base.get("failed_rule") != _PREFILTER_FAILURE:
        return base

    measured = dict(base.get("measured_values") or {})
    pct_change = _number(measured, "pct_change", default=0.0) or 0.0
    volume = _number(measured, "volume", default=0.0) or 0.0
    if pct_change < EARLY_OPEN_MIN_PCT_CHANGE or volume < EARLY_OPEN_MIN_VOLUME:
        return base

    decision = deepcopy(base)
    decision["passed"] = True
    decision["failed_rule"] = None
    decision["failed_metrics"] = []
    decision["reason"] = (
        "passed prefilter via early-open ignition "
        f"(>={EARLY_OPEN_MIN_PCT_CHANGE:g}% and >={EARLY_OPEN_MIN_VOLUME:,.0f} shares)"
    )
    thresholds = dict(decision.get("thresholds") or {})
    thresholds["early_open_exception"] = {
        "window_et": "09:30-09:45",
        "min_pct_change": EARLY_OPEN_MIN_PCT_CHANGE,
        "min_volume": EARLY_OPEN_MIN_VOLUME,
    }
    decision["thresholds"] = thresholds
    return decision


def _halted(record: dict) -> bool:
    if any(
        record.get(key) is True
        for key in ("halted", "is_halted", "suspended", "is_suspended")
    ):
        return True
    text = " ".join(
        str(record.get(key) or "")
        for key in ("halt_status", "trading_status", "market_status", "status_reason")
    ).lower()
    return "halt" in text or "suspend" in text


def _timeframe(record: dict, label: str) -> dict:
    frames = record.get("timeframes") or {}
    value = frames.get(label) if isinstance(frames, dict) else None
    return dict(value) if isinstance(value, dict) else {}


def _current_attention(record: dict) -> bool:
    try:
        from .gs309_current_attention_mission import current_attention_provenance

        if current_attention_provenance(record):
            return True
    except Exception:
        pass
    return bool(
        str(record.get("headline") or "").strip()
        or record.get("fresh_news")
        or record.get("news_catalyst")
        or record.get("has_catalyst")
        or record.get("catalyst_confirmed")
    )


def _supporting_flow(record: dict) -> bool:
    volume = _number(record, "volume", default=0.0) or 0.0
    participation = _number(
        record, "participation_surge_score", "participation_score", default=0.0
    ) or 0.0
    expansion = _number(record, "expansion_quality", "expansion_score", default=0.0) or 0.0
    volume_acceleration = _number(record, "volume_acceleration", default=0.0) or 0.0
    dollar_flow = _number(
        record, "dollar_flow_acceleration_5m", "dollar_flow_acceleration", default=0.0
    ) or 0.0
    return bool(
        volume >= 100_000
        or participation >= 20.0
        or expansion >= 40.0
        or volume_acceleration >= 1.0
        or dollar_flow >= 1.25
        or _current_attention(record)
    )


def three_minute_confirmation(record: dict) -> dict:
    """Consume GS378's deterministic 3m line-cross as maturation evidence."""
    events = record.get("st_vwap_cross_events") or {}
    event = dict(events.get("3m") or {}) if isinstance(events, dict) else {}
    age = _number(event, "age_seconds")
    fresh = bool(
        event.get("crossed")
        and (
            event.get("new") is True
            or (age is not None and 0.0 <= age <= THREE_MINUTE_NEW_SECONDS)
        )
    )

    one = _timeframe(record, "1m")
    three = _timeframe(record, "3m")
    one_constructive = bool(one.get("supertrend") and one.get("above_vwap"))
    three_constructive = bool(three.get("supertrend") and three.get("above_vwap"))
    relation = str(record.get("vwap_relation") or "").strip().lower()
    distance = _number(record, "vwap_distance_pct")
    above_vwap = relation == "above" or (distance is not None and distance >= 0.0)
    supported = _supporting_flow(record)

    active = bool(
        fresh
        and not _halted(record)
        and above_vwap
        and one_constructive
        and three_constructive
        and supported
    )
    return {
        "active": active,
        "crossed": bool(event.get("crossed")),
        "new": bool(event.get("new")),
        "timestamp": event.get("timestamp"),
        "age_seconds": age,
        "cross_price": _number(event, "price"),
        "supertrend_value": _number(event, "supertrend_value"),
        "vwap_value": _number(event, "vwap_value"),
        "one_minute_constructive": one_constructive,
        "three_minute_constructive": three_constructive,
        "supporting_flow": supported,
        "vwap_distance_pct": distance,
    }


def _state_with_three_minute_confirmation(original, record: dict) -> dict:
    from . import gs310_unified_opportunity_state as unified

    base = original(record)
    confirmation = three_minute_confirmation(record)
    if not confirmation["active"]:
        return base
    if base.get("state") in {unified.HALTED, unified.WATCH_FOR_ENTRY}:
        return base

    view = deepcopy(base)
    provenance = list(view.get("attention_provenance") or [])
    if _CONFIRMATION_PROVENANCE not in provenance:
        provenance.append(_CONFIRMATION_PROVENANCE)
    view["attention_provenance"] = provenance
    view["three_minute_st_vwap_confirmation"] = confirmation

    distance = confirmation.get("vwap_distance_pct")
    if distance is not None and distance > LOOK_NOW_MAX_VWAP_DISTANCE_PCT:
        # Confirmation deserves attention, but never erase the anti-chase state.
        view["state"] = unified.CHASE_WAIT
        view["color"] = unified.STATE_COLORS[unified.CHASE_WAIT]
        view["reason"] = (
            "3m SuperTrend just crossed above VWAP, confirming trend maturation, "
            f"but price is {distance:.1f}% above VWAP."
        )
        view["next_step"] = (
            "LOOK NOW for continuation context, but DO NOT CHASE. The existing VWAP "
            "anti-chase guard remains authoritative; wait for a constructive reset."
        )
        return view

    view["state"] = unified.LOOK_NOW
    view["color"] = unified.STATE_COLORS[unified.LOOK_NOW]
    view["reason"] = (
        "3m confirmation: SuperTrend just crossed above VWAP while 1m and 3m "
        "price/trend structure remain constructive."
    )
    view["next_step"] = (
        "Open the chart now. This is maturation evidence, not entry authority; "
        "normal participation, expansion, readiness, and VWAP guards still decide the trade."
    )
    return view


def _confirmation_change(record: dict) -> dict | None:
    evidence = three_minute_confirmation(record)
    if not evidence.get("active"):
        return None
    symbol = str(record.get("symbol") or "").strip().upper()
    if not symbol:
        return None
    timestamp = str(evidence.get("timestamp") or "unknown")
    return {
        "symbol": symbol,
        # Include the canonical event timestamp in the signature so a later, genuinely
        # different 3m crossover can alert again after an earlier one was deduplicated.
        "from": f"3M CROSS@{timestamp}",
        "to": "3M ST/VWAP CONFIRMATION",
    }


def _confirmation_phrase(records: list[dict]) -> str:
    for record in records or []:
        evidence = three_minute_confirmation(record)
        if not evidence.get("active"):
            continue
        symbol = str(record.get("symbol") or "Symbol").strip().upper() or "SYMBOL"
        distance = evidence.get("vwap_distance_pct")
        if distance is not None and distance > LOOK_NOW_MAX_VWAP_DISTANCE_PCT:
            return (
                f"{symbol}. LOOK NOW. Three minute SuperTrend crossed above VWAP. "
                "Continuation confirmed, but extended. Do not chase."
            )
        return (
            f"{symbol}. LOOK NOW. Three minute SuperTrend crossed above VWAP. "
            "Trend maturation confirmed."
        )
    return ""


def _inherit(wrapper, wrapped) -> None:
    for name, value in getattr(wrapped, "__dict__", {}).items():
        if name.startswith("_gs") and not hasattr(wrapper, name):
            setattr(wrapper, name, value)


def _install_prefilter() -> None:
    from . import discovery, flight_recorder

    current = flight_recorder.prefilter_decision
    if getattr(current, "_gs455_early_open_ignition", False):
        discovery.prefilter_decision = current
        return

    @wraps(current)
    def prefilter_decision(symbol: str, snapshot: dict, settings) -> dict:
        return _early_open_prefilter_decision(current, symbol, snapshot, settings)

    _inherit(prefilter_decision, current)
    prefilter_decision._gs455_early_open_ignition = True
    prefilter_decision._gs455_original = current
    flight_recorder.prefilter_decision = prefilter_decision
    # mide.discovery imported the callable by name, so rebind that exact live global too.
    discovery.prefilter_decision = prefilter_decision


def _install_state() -> None:
    from . import gs310_unified_opportunity_state as unified
    from . import gs311_unified_voice as voice
    from . import gs314_state_consistency as consistency
    from . import gs363_operator_attention_hierarchy as hierarchy

    current = unified.opportunity_state
    if getattr(current, "_gs455_three_minute_confirmation", False):
        calibrated = current
    else:
        original = current

        @wraps(original)
        def calibrated(record: dict) -> dict:
            return _state_with_three_minute_confirmation(original, record)

        _inherit(calibrated, current)
        calibrated._gs455_three_minute_confirmation = True
        calibrated._gs455_original = original
        unified.opportunity_state = calibrated

    # Keep every already-imported trader-facing state binding on one canonical truth.
    voice.opportunity_state = calibrated
    consistency.opportunity_state = calibrated
    hierarchy.opportunity_state = calibrated


def _install_alert_priority() -> None:
    from . import escalation
    from .gs365_chime_semantic_classifier import semantic_chime_count

    current_changes = escalation.escalation_state_changes
    if not getattr(current_changes, "_gs455_three_minute_confirmation", False):
        @wraps(current_changes)
        def state_changes(records: list[dict]) -> list[dict]:
            rows = list(records or [])
            existing = list(current_changes(rows))
            additions = [change for row in rows if (change := _confirmation_change(row))]
            if not additions:
                return existing
            keys = {
                (
                    str(item.get("symbol") or "").upper(),
                    str(item.get("from") or ""),
                    str(item.get("to") or ""),
                )
                for item in existing
            }
            # Preserve existing entry transitions at the front; confirmation is tier 2.
            for change in additions:
                key = (change["symbol"], change["from"], change["to"])
                if key not in keys:
                    existing.append(change)
                    keys.add(key)
            return existing

        _inherit(state_changes, current_changes)
        state_changes._gs455_three_minute_confirmation = True
        state_changes._gs455_original = current_changes
        escalation.escalation_state_changes = state_changes

    current_phrase = escalation.escalation_alert_phrase
    if not getattr(current_phrase, "_gs455_three_minute_confirmation", False):
        @wraps(current_phrase)
        def alert_phrase(records: list[dict]) -> str:
            rows = list(records or [])
            existing = str(current_phrase(rows) or "")
            confirmation = _confirmation_phrase(rows)
            if not confirmation:
                return existing
            # Existing tier-3 entry urgency always outranks this tier-2 maturation pulse.
            if existing and semantic_chime_count(existing) >= 3:
                return existing
            return confirmation

        _inherit(alert_phrase, current_phrase)
        alert_phrase._gs455_three_minute_confirmation = True
        alert_phrase._gs455_original = current_phrase
        escalation.escalation_alert_phrase = alert_phrase


def install() -> None:
    """Install the bounded discovery exception and deterministic 3m attention pulse."""
    _install_prefilter()
    _install_state()
    _install_alert_priority()

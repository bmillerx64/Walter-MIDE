"""GS455: admit early ignition and promote ordered ST/VWAP maturation.

RETO live validation on 2026-09-15 exposed two connected timing gaps.

First, Webull surfaced RETO during the first minutes after the open while it was still
below Walter's ordinary 3% OR 100k-share prefilter. Second, the move matured through a
clear timeframe sequence: 30s tripwire/flip -> 1m ST/VWAP cross -> 3m cross ->
5m/10m/15m crosses. Walter already owns this maturation architecture in GS421/GS423,
but that layer is observational and primarily retains bullish SuperTrend flips. The
literal ST-line/VWAP-line cascade was not promoted to operator attention.

GS455 sharpens the established architecture instead of building a parallel engine:

* 09:30-09:45 ET only, an already-discovered symbol may survive the cheap prefilter at
  >=2% AND >=15,000 shares. The ordinary prefilter resumes at 09:45.
* GS423's existing 1m/3m/5m/10m SuperTrend calculations retain literal line-cross
  metadata at zero additional ST cost. GS421's existing 15m study calculation does the
  same. GS378 remains canonical for 1m/3m crossover truth.
* Walter's established 30s tripwire/flip is the first rung; 1m is ignition, 3m is
  confirmation, and 5m/10m/15m are persistence/maturation.
* A newly reached ordered rung can create one tier-2 LOOK NOW operator pulse. Existing
  WATCH FOR ENTRY/entry authority wins, HALTED wins, and >5% VWAP extension remains
  CHASE / WAIT with explicit DO NOT CHASE guidance.

No provider request is added. No qualification, readiness, execution, order, float,
participation, expansion, or entry threshold is widened.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, time
from functools import wraps
import math
from typing import Any

EARLY_OPEN_START = time(9, 30)
EARLY_OPEN_END = time(9, 45)
EARLY_OPEN_MIN_PCT_CHANGE = 2.0
EARLY_OPEN_MIN_VOLUME = 15_000.0

CROSSOVER_LADDER = ("30s", "1m", "3m", "5m", "10m", "15m")
_NEW_WINDOWS_SECONDS = {
    "30s": 90.0,
    "1m": 120.0,
    "3m": 240.0,
    "5m": 360.0,
    "10m": 660.0,
    "15m": 960.0,
}
_RECENT_WINDOWS_SECONDS = {
    "30s": 10 * 60.0,
    "1m": 15 * 60.0,
    "3m": 20 * 60.0,
    "5m": 30 * 60.0,
    "10m": 50 * 60.0,
    "15m": 75 * 60.0,
}
LOOK_NOW_MAX_VWAP_DISTANCE_PCT = 5.0

_PREFILTER_FAILURE = "Percent change and average volume below thresholds"
_PROGRESSION_PROVENANCE = "ST_VWAP_CROSSOVER_PROGRESSION"


def _number(record: dict, *keys: str, default: float | None = None) -> float | None:
    for key in keys:
        value = record.get(key)
        if value is None or value == "":
            continue
        try:
            number = float(value)
        except (TypeError, ValueError):
            continue
        if math.isfinite(number):
            return number
    return default


def _finite(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


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


def _line_cross_event(
    frame,
    vwap,
    st_line,
    trend,
    label: str,
    *,
    latest_source_time,
) -> dict:
    """Retain a literal ST-line/VWAP-line cross from an already-paid ST pass."""
    if frame is None or getattr(frame, "empty", True) or len(frame) < 2:
        return {
            "timeframe": label,
            "crossed": False,
            "recent": False,
            "new": False,
            "timestamp": None,
            "age_seconds": None,
            "current_confirmed": False,
        }

    close = frame["close"].astype(float)
    valid = st_line.notna() & vwap.notna()
    bullish = trend.fillna(False).astype(bool)
    line_delta = st_line - vwap
    mask = (
        valid
        & (line_delta.shift(1) < 0)
        & (line_delta >= 0)
        & bullish
        & (close >= vwap)
    )
    hits = list(mask[mask.fillna(False)].index)
    cross_time = hits[-1] if hits else None
    age = (
        max(0.0, (latest_source_time - cross_time).total_seconds())
        if cross_time is not None and latest_source_time is not None
        else None
    )

    latest_st = _finite(st_line.iloc[-1]) if len(st_line) else None
    latest_vwap = _finite(vwap.iloc[-1]) if len(vwap) else None
    latest_close = _finite(close.iloc[-1]) if len(close) else None
    current_confirmed = bool(
        latest_st is not None
        and latest_vwap is not None
        and latest_close is not None
        and bool(bullish.iloc[-1])
        and latest_close >= latest_vwap
        and latest_st >= latest_vwap
    )

    event = {
        "timeframe": label,
        "crossed": cross_time is not None,
        "recent": bool(
            age is not None and age <= _RECENT_WINDOWS_SECONDS[label]
        ),
        "new": bool(age is not None and age <= _NEW_WINDOWS_SECONDS[label]),
        "timestamp": cross_time.isoformat() if cross_time is not None else None,
        "age_seconds": round(age, 1) if age is not None else None,
        "current_confirmed": current_confirmed,
        # Normalize non-ready ST values to None. Never leak NaN into scan evidence;
        # NaN is not self-equal and breaks deterministic scan/replay comparisons.
        "latest_supertrend_value": (
            round(latest_st, 6) if latest_st is not None else None
        ),
        "latest_vwap_value": (
            round(latest_vwap, 6) if latest_vwap is not None else None
        ),
    }
    if cross_time is not None:
        event.update(
            {
                "supertrend_value": round(float(st_line.loc[cross_time]), 6),
                "vwap_value": round(float(vwap.loc[cross_time]), 6),
                "price": round(float(close.loc[cross_time]), 6),
                "volume": round(float(frame.loc[cross_time, "volume"]), 2),
            }
        )
    return event


def _confirmation_details_with_line_cross(day, primary_series) -> tuple[int, dict]:
    """GS423 confirmation pass plus literal cross metadata, with no extra ST call."""
    from . import gs378_live_vwap_st_crossover as gs378

    confirmations = 0
    details: dict[str, dict] = {}
    latest_source_time = day.index[-1] if day is not None and not day.empty else None

    for label in ("1m", "3m", "5m", "10m"):
        tf = gs378._timeframe_frame(day, label)
        if len(tf) < 20:
            continue
        vwap = gs378._timeframe_vwap(primary_series, label).reindex(tf.index)
        st_line, trend = gs378.supertrend(tf, 10, 3)
        close = tf["close"].astype(float)
        latest_vwap = gs378._finite_number(vwap.iloc[-1]) if len(vwap) else None
        latest_close = gs378._finite_number(close.iloc[-1]) if len(close) else None
        bullish = bool(len(trend) and trend.iloc[-1])
        above_vwap = bool(
            latest_vwap is not None
            and latest_close is not None
            and latest_close >= latest_vwap
        )
        if bullish and above_vwap:
            confirmations += 1

        valid = st_line.notna() & vwap.notna()
        bullish_series = trend.fillna(False).astype(bool)
        prior_bullish = bullish_series.shift(1).fillna(False).astype(bool)
        flip_mask = valid & bullish_series & (~prior_bullish) & (close >= vwap)
        flip_time = gs378._latest_event(flip_mask)
        flip_age = (
            max(0.0, (latest_source_time - flip_time).total_seconds())
            if flip_time is not None and latest_source_time is not None
            else None
        )

        detail = {
            "above_vwap": above_vwap,
            "supertrend": bullish,
            "timeframe": label,
            "data_available": bool(valid.any()),
            "current_supertrend_bullish": bullish,
            "current_above_vwap": above_vwap,
            "current_confirmed": bool(bullish and above_vwap),
            "current_close": latest_close,
            "current_vwap": latest_vwap,
            "bullish_flip_timestamp": (
                flip_time.isoformat() if flip_time is not None else None
            ),
            "bullish_flip_age_seconds": (
                round(flip_age, 1) if flip_age is not None else None
            ),
            "st_vwap_line_cross": _line_cross_event(
                tf,
                vwap,
                st_line,
                trend,
                label,
                latest_source_time=latest_source_time,
            ),
        }
        if flip_time is not None:
            flip_price = _finite(close.loc[flip_time])
            flip_vwap = _finite(vwap.loc[flip_time])
            detail.update(
                {
                    "price_at_flip": flip_price,
                    "vwap_at_flip": flip_vwap,
                    "vwap_distance_at_flip_pct": (
                        round((flip_price - flip_vwap) / flip_vwap * 100.0, 4)
                        if flip_price is not None and flip_vwap not in (None, 0)
                        else None
                    ),
                    "supertrend_at_flip": _finite(st_line.loc[flip_time]),
                    "volume_at_flip": _finite(tf.loc[flip_time, "volume"]),
                }
            )
        details[label] = detail

    return confirmations, details


def _timeframe_event_with_line_cross(day, primary_1m, label: str) -> dict:
    """GS421 timeframe event plus literal cross metadata from the same ST pass."""
    from . import gs421_multitimeframe_convergence_recorder as gs421
    from .indicators import supertrend

    tf = gs421._timeframe_frame(day, label)
    vwap = gs421._timeframe_vwap(primary_1m, label).reindex(tf.index)
    if len(tf) < 2 or vwap.empty:
        return {
            "timeframe": label,
            "data_available": False,
            "current_supertrend_bullish": False,
            "current_above_vwap": False,
            "current_confirmed": False,
            "bullish_flip_timestamp": None,
            "bullish_flip_age_seconds": None,
            "st_vwap_line_cross": {
                "timeframe": label,
                "crossed": False,
                "recent": False,
                "new": False,
                "timestamp": None,
                "age_seconds": None,
                "current_confirmed": False,
            },
        }

    st_line, trend = supertrend(tf, 10, 3)
    bullish = trend.fillna(False).astype(bool)
    prior_bullish = bullish.shift(1).fillna(False).astype(bool)
    close = tf["close"].astype(float)
    valid = st_line.notna() & vwap.notna()
    flip_mask = valid & bullish & (~prior_bullish) & (close >= vwap)
    hits = list(flip_mask[flip_mask].index)
    flip_time = hits[-1] if hits else None

    latest_vwap = _finite(vwap.iloc[-1]) if len(vwap) else None
    latest_close = _finite(close.iloc[-1])
    current_bullish = bool(len(bullish) and bullish.iloc[-1])
    current_above_vwap = bool(
        latest_close is not None
        and latest_vwap is not None
        and latest_close >= latest_vwap
    )

    event = {
        "timeframe": label,
        "data_available": bool(valid.any()),
        "current_supertrend_bullish": current_bullish,
        "current_above_vwap": current_above_vwap,
        "current_confirmed": bool(current_bullish and current_above_vwap),
        "current_close": latest_close,
        "current_vwap": latest_vwap,
        "bullish_flip_timestamp": flip_time.isoformat() if flip_time is not None else None,
        "bullish_flip_age_seconds": None,
        "st_vwap_line_cross": _line_cross_event(
            tf,
            vwap,
            st_line,
            trend,
            label,
            latest_source_time=day.index[-1],
        ),
    }
    if flip_time is not None:
        age = max(0.0, (day.index[-1] - flip_time).total_seconds())
        flip_price = _finite(close.loc[flip_time])
        flip_vwap = _finite(vwap.loc[flip_time])
        event.update(
            {
                "bullish_flip_age_seconds": round(age, 1),
                "price_at_flip": flip_price,
                "vwap_at_flip": flip_vwap,
                "vwap_distance_at_flip_pct": (
                    round((flip_price - flip_vwap) / flip_vwap * 100.0, 4)
                    if flip_price is not None and flip_vwap not in (None, 0)
                    else None
                ),
                "supertrend_at_flip": _finite(st_line.loc[flip_time]),
                "volume_at_flip": _finite(tf.loc[flip_time, "volume"]),
            }
        )
    return event


def _install_existing_maturation_source() -> None:
    """Converge GS423 first, then enrich its already-paid ST passes."""
    from . import gs378_live_vwap_st_crossover as gs378
    from . import gs421_multitimeframe_convergence_recorder as gs421
    from . import gs423_convergence_handoff_efficiency as gs423

    # GS455 can be reached from the late GS454 boundary before startup's explicit
    # GS423 call. Install GS423 now; the later startup call is idempotent.
    gs423.install()

    if not getattr(gs378._confirmation_details, "_gs455_line_cross", False):
        _confirmation_details_with_line_cross._gs455_line_cross = True
        _confirmation_details_with_line_cross._gs455_original = gs378._confirmation_details
        gs378._confirmation_details = _confirmation_details_with_line_cross

    if not getattr(gs421._timeframe_event, "_gs455_line_cross", False):
        _timeframe_event_with_line_cross._gs455_line_cross = True
        _timeframe_event_with_line_cross._gs455_original = gs421._timeframe_event
        gs421._timeframe_event = _timeframe_event_with_line_cross


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


def _current_attention(record: dict) -> bool:
    reasons = " ".join(str(item) for item in (record.get("discovery_reasons") or []))
    if "webull native:" in reasons.lower():
        return True
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
    expansion = _number(
        record, "expansion_quality", "expansion_score", default=0.0
    ) or 0.0
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


def _timestamp(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


def _thirty_second_rung(record: dict) -> dict:
    tripwire = record.get("thirty_second_tripwire") or {}
    stamp = (
        record.get("supertrend_30s_last_flip_timestamp")
        or tripwire.get("last_flip_timestamp")
    )
    age = _number(
        record,
        "supertrend_30s_last_flip_age_seconds",
        "supertrend_30s_flip_age_seconds",
    )
    if age is None:
        age = _number(tripwire, "last_flip_age_seconds")
    bullish = bool(
        record.get("supertrend_30s_bullish")
        or tripwire.get("supertrend_bullish")
    )
    active = bool(stamp and bullish)
    return {
        "timeframe": "30s",
        "crossed": active,
        "recent": bool(active and age is not None and age <= _RECENT_WINDOWS_SECONDS["30s"]),
        "new": bool(active and age is not None and age <= _NEW_WINDOWS_SECONDS["30s"]),
        "timestamp": stamp,
        "age_seconds": age,
        "current_confirmed": bullish,
        "kind": "canonical_30s_tripwire_flip",
    }


def _rung_event(record: dict, label: str) -> dict:
    if label == "30s":
        return _thirty_second_rung(record)

    if label in {"1m", "3m"}:
        canonical = dict((record.get("st_vwap_cross_events") or {}).get(label) or {})
        detail = dict((record.get("timeframes") or {}).get(label) or {})
        enriched = dict(detail.get("st_vwap_line_cross") or {})
        event = canonical or enriched
        if canonical and enriched:
            event = dict(canonical)
            event["current_confirmed"] = enriched.get(
                "current_confirmed",
                bool(detail.get("above_vwap") and detail.get("supertrend")),
            )
        elif event:
            event.setdefault(
                "current_confirmed",
                bool(detail.get("above_vwap") and detail.get("supertrend")),
            )
        return event

    if label in {"5m", "10m"}:
        detail = dict((record.get("timeframes") or {}).get(label) or {})
        return dict(detail.get("st_vwap_line_cross") or {})

    maturation = record.get("multitimeframe_maturation") or {}
    detail = dict((maturation.get("timeframes") or {}).get("15m") or {})
    return dict(detail.get("st_vwap_line_cross") or {})


def _market_evidence():
    from mide.authorities import market_evidence

    return market_evidence


def crossover_progression(record: dict) -> dict:
    """Compatibility facade for authoritative ordered maturation evidence."""
    current = getattr(
        _market_evidence(),
        "crossover_progression",
        None,
    )
    if not callable(current):
        return {
            "ladder": list(CROSSOVER_LADDER),
            "active_rungs": [],
            "fresh_rungs": [],
            "depth": 0,
            "ordered": True,
            "highest_rung": None,
            "latest_new_rung": None,
            "stage": "NONE",
            "sequence": "",
            "events": {},
        }
    return current(record)


def progression_signal(record: dict) -> dict:
    """Compatibility facade for authoritative fresh-rung evidence."""
    current = getattr(
        _market_evidence(),
        "progression_signal",
        None,
    )
    if not callable(current):
        return {
            "active": False,
            "new_rung": None,
            "timestamp": None,
            "stage": "NONE",
            "sequence": "",
            "depth": 0,
            "ordered": True,
            "supporting_flow": False,
            "vwap_distance_pct": _number(
                record,
                "vwap_distance_pct",
            ),
        }
    return current(record)

def _state_with_progression(original, record: dict) -> dict:
    from . import gs310_unified_opportunity_state as unified

    base = original(record)
    signal = progression_signal(record)
    if not signal["active"]:
        return base
    if base.get("state") in {unified.HALTED, unified.WATCH_FOR_ENTRY}:
        return base

    view = deepcopy(base)
    provenance = list(view.get("attention_provenance") or [])
    if _PROGRESSION_PROVENANCE not in provenance:
        provenance.append(_PROGRESSION_PROVENANCE)
    view["attention_provenance"] = provenance
    view["st_vwap_progression"] = crossover_progression(record)

    rung = str(signal.get("new_rung") or "").upper()
    sequence = signal.get("sequence") or rung
    distance = signal.get("vwap_distance_pct")
    if distance is not None and distance > LOOK_NOW_MAX_VWAP_DISTANCE_PCT:
        view["state"] = unified.CHASE_WAIT
        view["color"] = unified.STATE_COLORS[unified.CHASE_WAIT]
        view["reason"] = (
            f"ST/VWAP maturation reached {rung}; {sequence}. "
            f"Price is already {distance:.1f}% above VWAP."
        )
        view["next_step"] = (
            "LOOK NOW for continuation context, but DO NOT CHASE. The VWAP anti-chase "
            "guard remains authoritative; wait for a constructive reset."
        )
        return view

    view["state"] = unified.LOOK_NOW
    view["color"] = unified.STATE_COLORS[unified.LOOK_NOW]
    view["reason"] = f"ST/VWAP maturation reached {rung}; {sequence}."
    view["next_step"] = (
        "Open the chart now. The maturation ladder is operator-attention evidence, not "
        "entry authority; normal participation, expansion, readiness, and VWAP guards "
        "still decide the trade."
    )
    return view


def _progression_change(record: dict) -> dict | None:
    signal = progression_signal(record)
    if not signal.get("active"):
        return None
    symbol = str(record.get("symbol") or "").strip().upper()
    if not symbol:
        return None
    rung = str(signal.get("new_rung") or "").upper()
    stamp = str(signal.get("timestamp") or "unknown")
    return {
        "symbol": symbol,
        "from": f"{rung} CROSS@{stamp}",
        "to": f"ST/VWAP MATURATION {rung}",
    }


def _spoken_rung(label: str) -> str:
    return {
        "30s": "30 second",
        "1m": "1 minute",
        "3m": "3 minute",
        "5m": "5 minute",
        "10m": "10 minute",
        "15m": "15 minute",
    }.get(label, label)


def _progression_phrase(records: list[dict]) -> str:
    choices = []
    for record in records or []:
        signal = progression_signal(record)
        if signal.get("active"):
            rank = CROSSOVER_LADDER.index(signal["new_rung"])
            choices.append((rank, record, signal))
    if not choices:
        return ""

    _, record, signal = max(choices, key=lambda item: item[0])
    symbol = str(record.get("symbol") or "Symbol").strip().upper() or "SYMBOL"
    rung = _spoken_rung(str(signal.get("new_rung") or ""))
    stage = str(signal.get("stage") or "").lower()
    phrase = (
        f"{symbol}. LOOK NOW. SuperTrend VWAP maturation reached {rung}. "
        f"{stage.capitalize()} advancing."
    )
    distance = signal.get("vwap_distance_pct")
    if distance is not None and distance > LOOK_NOW_MAX_VWAP_DISTANCE_PCT:
        phrase += " Extended. Do not chase."
    return phrase


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
    discovery.prefilter_decision = prefilter_decision


def _install_state() -> None:
    from . import gs310_unified_opportunity_state as unified
    from . import gs311_unified_voice as voice
    from . import gs314_state_consistency as consistency
    from . import gs363_operator_attention_hierarchy as hierarchy

    current = unified.opportunity_state
    if getattr(current, "_gs455_crossover_progression", False):
        calibrated = current
    else:
        original = current

        @wraps(original)
        def calibrated(record: dict) -> dict:
            return _state_with_progression(original, record)

        _inherit(calibrated, current)
        calibrated._gs455_crossover_progression = True
        calibrated._gs455_original = original
        unified.opportunity_state = calibrated

    voice.opportunity_state = calibrated
    consistency.opportunity_state = calibrated
    hierarchy.opportunity_state = calibrated


def _install_alert_priority() -> None:
    from . import escalation
    from .gs365_chime_semantic_classifier import semantic_chime_count

    current_changes = escalation.escalation_state_changes
    if not getattr(current_changes, "_gs455_crossover_progression", False):
        @wraps(current_changes)
        def state_changes(records: list[dict]) -> list[dict]:
            rows = list(records or [])
            existing = list(current_changes(rows))
            additions = [
                change for row in rows if (change := _progression_change(row))
            ]
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
            for change in additions:
                key = (change["symbol"], change["from"], change["to"])
                if key not in keys:
                    existing.append(change)
                    keys.add(key)
            return existing

        _inherit(state_changes, current_changes)
        state_changes._gs455_crossover_progression = True
        state_changes._gs455_original = current_changes
        escalation.escalation_state_changes = state_changes

    current_phrase = escalation.escalation_alert_phrase
    if not getattr(current_phrase, "_gs455_crossover_progression", False):
        @wraps(current_phrase)
        def alert_phrase(records: list[dict]) -> str:
            rows = list(records or [])
            existing = str(current_phrase(rows) or "")
            progression = _progression_phrase(rows)
            if not progression:
                return existing
            if existing and semantic_chime_count(existing) >= 3:
                return existing
            return progression

        _inherit(alert_phrase, current_phrase)
        alert_phrase._gs455_crossover_progression = True
        alert_phrase._gs455_original = current_phrase
        escalation.escalation_alert_phrase = alert_phrase


def install() -> None:
    """Install bounded early admission plus existing-stack maturation priority."""
    _install_existing_maturation_source()
    _install_prefilter()
    _install_state()
    _install_alert_priority()

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
    current = getattr(
        _market_evidence(),
        "maturation_finite",
        None,
    )
    if callable(current):
        return current(value)
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None

def _discovery_news():
    from mide.authorities import discovery_news

    return discovery_news


def _market_now():
    current = getattr(
        _discovery_news(),
        "early_open_market_now",
        None,
    )
    if callable(current):
        return current()
    from .time_service import eastern_time
    return eastern_time()

def _inside_early_open_window() -> bool:
    current = getattr(
        _discovery_news(),
        "early_open_inside_window",
        None,
    )
    if callable(current):
        return bool(current())
    now = _market_now()
    current_time = now.time().replace(tzinfo=None)
    return (
        EARLY_OPEN_START
        <= current_time
        < EARLY_OPEN_END
    )

def _early_open_prefilter_decision(
    original,
    symbol: str,
    snapshot: dict,
    settings,
) -> dict:
    current = getattr(
        _discovery_news(),
        "early_open_prefilter_decision",
        None,
    )
    if not callable(current):
        return original(
            symbol,
            snapshot,
            settings,
        )
    return current(
        original,
        symbol,
        snapshot,
        settings,
    )

def _line_cross_event(
    frame,
    vwap,
    st_line,
    trend,
    label: str,
    *,
    latest_source_time,
) -> dict:
    current = getattr(
        _market_evidence(),
        "maturation_line_cross_event",
        None,
    )
    if not callable(current):
        return {
            "timeframe": label,
            "crossed": False,
            "recent": False,
            "new": False,
            "timestamp": None,
            "age_seconds": None,
            "current_confirmed": False,
        }
    return current(
        frame,
        vwap,
        st_line,
        trend,
        label,
        latest_source_time=latest_source_time,
    )

def _confirmation_details_with_line_cross(
    day,
    primary_series,
) -> tuple[int, dict]:
    current = getattr(
        _market_evidence(),
        "maturation_confirmation_details_with_line_cross",
        None,
    )
    if not callable(current):
        return 0, {}
    return current(day, primary_series)

def _timeframe_event_with_line_cross(
    day,
    primary_1m,
    label: str,
) -> dict:
    current = getattr(
        _market_evidence(),
        "maturation_timeframe_event_with_line_cross",
        None,
    )
    if not callable(current):
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
    return current(day, primary_1m, label)

def _install_existing_maturation_source() -> None:
    current = getattr(
        _market_evidence(),
        "install_maturation_line_cross_enrichment",
        None,
    )
    if callable(current):
        current()

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

def _thesis_state():
    from mide.authorities import thesis_state

    return thesis_state


def _state_with_progression(
    original,
    record: dict,
) -> dict:
    current = getattr(
        _thesis_state(),
        "progression_opportunity_state",
        None,
    )
    if not callable(current):
        return original(record)
    return current(
        original,
        record,
    )

def _presentation_audio():
    from mide.authorities import presentation_audio

    return presentation_audio


def _progression_change(
    record: dict,
) -> dict | None:
    current = getattr(
        _presentation_audio(),
        "progression_change",
        None,
    )
    if not callable(current):
        return None
    return current(record)

def _spoken_rung(label: str) -> str:
    current = getattr(
        _presentation_audio(),
        "spoken_progression_rung",
        None,
    )
    if not callable(current):
        return label
    return current(label)

def _progression_phrase(
    records: list[dict],
) -> str:
    current = getattr(
        _presentation_audio(),
        "progression_audio_phrase",
        None,
    )
    if not callable(current):
        return ""
    return current(records)

def _inherit(wrapper, wrapped) -> None:
    for name, value in getattr(wrapped, "__dict__", {}).items():
        if name.startswith("_gs") and not hasattr(wrapper, name):
            setattr(wrapper, name, value)


def _install_prefilter() -> None:
    current = getattr(
        _discovery_news(),
        "install_early_open_ignition_admission",
        None,
    )
    if callable(current):
        current()

def _install_state() -> None:
    current = getattr(
        _thesis_state(),
        "install_progression_state",
        None,
    )
    if callable(current):
        current()

def _install_alert_priority() -> None:
    current = getattr(
        _presentation_audio(),
        "install_progression_alert_priority",
        None,
    )
    if callable(current):
        current()

def install() -> None:
    """Install bounded early admission plus existing-stack maturation priority."""
    _install_existing_maturation_source()
    _install_prefilter()
    _install_state()
    _install_alert_priority()

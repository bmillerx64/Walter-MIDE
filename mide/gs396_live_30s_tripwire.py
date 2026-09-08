"""GS396: promote genuine Webull 30-second SuperTrend from evidence to tripwire.

Walter already receives official Webull TICK messages (GS379), reconstructs genuine
closed 30-second OHLCV bars, and computes SuperTrend(10,3) on those bars (GS386).
Until GS396 that information was explicitly observational only: Walter could record
what the 30-second chart did, but the live scanner did not use it to start looking.

GS396 makes the 30-second state the first domino in Walter's attention ladder:

    discovery -> 30s tripwire -> 1m primary ignition -> 3m confirmation

The 30-second signal is investigation authority, not entry authority. A fresh 30s
bullish flip can raise momentum/attention and start the sequential trend ladder, but
Walter's existing entry trigger continues to use the pre-GS396 1-minute/generic ST
signal. GS393's 1m LOOK NOW ignition and GS394's 1m/3m consolidation re-arm remain
unchanged.

Safety contract:
- only completed genuine Webull 30s bars are used;
- a 30s flip is fresh for 180 seconds (three nominal 60-second scan cycles);
- 30s state never substitutes for the 1m entry trigger;
- no price, float, catalyst, participation, expansion, VWAP, ranking, readiness,
  execution, or order threshold is loosened;
- when the stream is unavailable or ST is not ready, legacy behavior is unchanged.
"""
from __future__ import annotations

from datetime import datetime, timezone
from functools import wraps
from statistics import median
from typing import Any

from .gs386_30s_observational_recorder import _annotated_rows

AUTHORITY = "LIVE_ATTENTION_TRIPWIRE"
SOURCE = "Webull OpenAPI TICK -> completed 30s bars -> ST(10,3)"
BAR_INTERVAL_SECONDS = 30
TRIPWIRE_FRESH_SECONDS = 180.0
BASELINE_BARS = 6


def _number(value: Any) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _utc(value: datetime | None) -> datetime:
    if value is None:
        return datetime.now(timezone.utc)
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _iso_from_ms(timestamp_ms: int | None) -> str | None:
    if timestamp_ms is None:
        return None
    return datetime.fromtimestamp(timestamp_ms / 1000.0, tz=timezone.utc).isoformat()


def _ratio(current: float | None, baseline_values: list[float]) -> float | None:
    if current is None:
        return None
    valid = [float(value) for value in baseline_values if value is not None and value > 0]
    if not valid:
        return None
    base = median(valid)
    if base <= 0:
        return None
    return round(float(current) / base, 4)


def tripwire_from_annotated(
    annotated: list[dict], scan_time: datetime | None = None
) -> dict[str, Any]:
    """Build authoritative 30s attention evidence from already-annotated closed bars."""
    ready = [dict(row) for row in annotated or [] if row.get("supertrend_ready")]
    if not ready:
        return {
            "available": False,
            "authority": AUTHORITY,
            "source": SOURCE,
            "fresh_flip": False,
        }

    latest = ready[-1]
    latest_state = str(latest.get("supertrend_state") or "").strip().lower()
    bullish = latest_state == "bullish"

    flip_row: dict | None = None
    for prior, current in zip(ready, ready[1:]):
        prior_state = str(prior.get("supertrend_state") or "").strip().lower()
        current_state = str(current.get("supertrend_state") or "").strip().lower()
        if prior_state != "bullish" and current_state == "bullish":
            flip_row = current

    flip_close_ms = None
    flip_age = None
    if flip_row is not None:
        raw_ms = flip_row.get("timestamp_ms")
        if raw_ms is not None:
            flip_close_ms = int(raw_ms) + BAR_INTERVAL_SECONDS * 1000
            now_ms = int(_utc(scan_time).timestamp() * 1000)
            flip_age = max(0.0, (now_ms - flip_close_ms) / 1000.0)

    fresh_flip = bool(
        bullish
        and flip_age is not None
        and 0.0 <= flip_age <= TRIPWIRE_FRESH_SECONDS
    )

    previous = ready[max(0, len(ready) - BASELINE_BARS - 1):-1]
    latest_volume = _number(latest.get("volume"))
    latest_close = _number(latest.get("close"))
    volume_acceleration = _ratio(
        latest_volume,
        [_number(row.get("volume")) or 0.0 for row in previous],
    )
    latest_dollar = (
        latest_volume * latest_close
        if latest_volume is not None and latest_close is not None
        else None
    )
    dollar_acceleration = _ratio(
        latest_dollar,
        [
            (_number(row.get("volume")) or 0.0) * (_number(row.get("close")) or 0.0)
            for row in previous
        ],
    )

    latest_start_ms = int(latest.get("timestamp_ms"))
    latest_close_ms = latest_start_ms + BAR_INTERVAL_SECONDS * 1000
    return {
        "available": True,
        "authority": AUTHORITY,
        "source": SOURCE,
        "bar_interval_seconds": BAR_INTERVAL_SECONDS,
        "supertrend_period": 10,
        "supertrend_multiplier": 3.0,
        "bullish": bullish,
        "fresh_flip": fresh_flip,
        "fresh_window_seconds": TRIPWIRE_FRESH_SECONDS,
        "last_flip_age_seconds": round(flip_age, 1) if flip_age is not None else None,
        "last_flip_timestamp": _iso_from_ms(flip_close_ms),
        "latest_closed_timestamp": _iso_from_ms(latest_close_ms),
        "latest_close": latest_close,
        "latest_volume": latest_volume,
        "supertrend_value": _number(latest.get("supertrend_10_3")),
        "volume_acceleration_30s": volume_acceleration,
        "dollar_flow_acceleration_30s": dollar_acceleration,
    }


def _active_provider():
    from .gs386_30s_observational_recorder import _active_provider as active_provider

    return active_provider()


def enrich_record_with_live_30s(
    source: dict,
    provider,
    scan_time: datetime | None = None,
) -> dict:
    """Attach real 30s tripwire fields without changing 1m/3m entry authority."""
    record = dict(source)
    symbol = str(record.get("symbol") or "").strip().upper()
    if not symbol or provider is None or not hasattr(provider, "stream_30s_bars"):
        return record

    rows = list(provider.stream_30s_bars(symbol) or [])
    tripwire = tripwire_from_annotated(_annotated_rows(rows), scan_time)
    if not tripwire.get("available"):
        return record

    record["thirty_second_tripwire"] = tripwire
    record["supertrend_30s_available"] = True
    record["supertrend_30s_authority"] = AUTHORITY
    record["supertrend_30s_source"] = SOURCE
    record["supertrend_30s_bullish"] = bool(tripwire.get("bullish"))
    record["supertrend_30s_last_flip_age_seconds"] = tripwire.get(
        "last_flip_age_seconds"
    )
    record["supertrend_30s_last_flip_timestamp"] = tripwire.get(
        "last_flip_timestamp"
    )
    record["volume_acceleration_30s"] = tripwire.get("volume_acceleration_30s")
    record["dollar_flow_acceleration_30s"] = tripwire.get(
        "dollar_flow_acceleration_30s"
    )

    # Canonical legacy fields are asserted only while the genuine 30s flip is fresh.
    # When it is not fresh, leave them absent so older fallback expressions continue
    # to see Walter's existing 1m/generic SuperTrend signal rather than a forced False.
    record.pop("supertrend_30s_flip", None)
    record.pop("supertrend_30s_flip_age_seconds", None)
    if tripwire.get("fresh_flip"):
        record["supertrend_30s_flip"] = True
        record["supertrend_30s_flip_age_seconds"] = tripwire.get(
            "last_flip_age_seconds"
        )

    return record


def enrich_records_with_live_30s(
    records,
    scan_time: datetime | None = None,
    provider=None,
) -> list[dict]:
    provider = _active_provider() if provider is None else provider
    if provider is None:
        return [dict(record) for record in records or []]
    return [
        enrich_record_with_live_30s(record, provider, scan_time)
        for record in (records or [])
    ]


def entry_authority_record(record: dict) -> dict:
    """Return the pre-GS396 entry view: real 30s tripwire cannot satisfy entry ST."""
    if not record.get("supertrend_30s_available"):
        return record
    view = dict(record)
    view.pop("supertrend_30s_flip", None)
    view.pop("supertrend_30s_flip_age_seconds", None)
    return view


def install() -> None:
    """Inject 30s tripwire before Scanner V2 while preserving 1m entry authority."""
    from . import scanner_v2 as scanner

    current_trigger = scanner.trigger_diagnostics
    if not getattr(current_trigger, "_gs396_1m_entry_authority", False):
        @wraps(current_trigger)
        def trigger_diagnostics(record: dict, prior: dict | None = None, scan_time=None):
            # Scanner V2 historically fell back to generic/1m supertrend_flip because
            # the real 30s field did not exist. Preserve that exact entry authority.
            result = current_trigger(entry_authority_record(record), prior, scan_time)
            if record.get("supertrend_30s_available"):
                result = dict(result)
                result["thirty_second_tripwire"] = dict(
                    record.get("thirty_second_tripwire") or {}
                )
                result["supertrend_authority"] = (
                    "30s investigation tripwire; 1m/generic flip remains entry authority"
                )
            return result

        trigger_diagnostics._gs396_1m_entry_authority = True
        trigger_diagnostics._gs396_original = current_trigger
        scanner.trigger_diagnostics = trigger_diagnostics

    current_trend_passed = scanner._trend_confirmation_passed
    if not getattr(current_trend_passed, "_gs396_live_30s_state", False):
        @wraps(current_trend_passed)
        def trend_confirmation_passed(record: dict, label: str) -> bool:
            if label == "30s" and record.get("supertrend_30s_available"):
                return bool(record.get("supertrend_30s_bullish"))
            return current_trend_passed(record, label)

        trend_confirmation_passed._gs396_live_30s_state = True
        trend_confirmation_passed._gs396_original = current_trend_passed
        scanner._trend_confirmation_passed = trend_confirmation_passed

    current_state = scanner._supertrend_state
    if not getattr(current_state, "_gs396_live_30s_state", False):
        @wraps(current_state)
        def supertrend_state(record: dict, label: str) -> str:
            if label == "30s" and record.get("supertrend_30s_available"):
                if record.get("supertrend_30s_flip"):
                    return "flipped green"
                return "green" if record.get("supertrend_30s_bullish") else "not green"
            return current_state(record, label)

        supertrend_state._gs396_live_30s_state = True
        supertrend_state._gs396_original = current_state
        scanner._supertrend_state = supertrend_state

    current_apply = scanner.apply_scanner_v2
    if not getattr(current_apply, "_gs396_live_30s_tripwire", False):
        @wraps(current_apply)
        def apply_scanner_v2(records, previous_by_symbol, scan_time=None):
            enriched = enrich_records_with_live_30s(records, scan_time)
            return current_apply(enriched, previous_by_symbol, scan_time)

        apply_scanner_v2._gs396_live_30s_tripwire = True
        apply_scanner_v2._gs396_original = current_apply
        scanner.apply_scanner_v2 = apply_scanner_v2

from __future__ import annotations

from dataclasses import dataclass
from datetime import time
from typing import Hashable

import pandas as pd

MARKET_OPEN = time(9, 30)
MARKET_CLOSE = time(16, 0)
MIN_EXPECTED_VOLUME = 1.0
_PROFILE_CACHE: dict[tuple[str, Hashable, int], dict[int, dict[str, float]]] = {}


@dataclass(frozen=True)
class VolumePaceMetrics:
    current_volume: float
    expected_volume: float
    volume_pace_ratio: float
    recent_5m_volume: float
    expected_5m_volume: float
    acceleration_ratio: float
    passed: bool
    status: str
    reason: str | None


def _minute_of_day(index: pd.DatetimeIndex) -> pd.Index:
    localized = (
        index.tz_convert("America/New_York")
        if index.tz is not None
        else index.tz_localize("America/New_York")
    )
    return localized.hour * 60 + localized.minute


def _regular_session(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame
    local = frame.copy()
    local.index = (
        local.index.tz_convert("America/New_York")
        if local.index.tz is not None
        else local.index.tz_localize("America/New_York")
    )
    return local.between_time(MARKET_OPEN, MARKET_CLOSE, inclusive="left")


def clear_volume_profile_cache() -> None:
    _PROFILE_CACHE.clear()


def historical_volume_profile(
    symbol: str, frame: pd.DataFrame, current_session_date=None
) -> dict[int, dict[str, float]]:
    """Return cached average cumulative and 5-minute volume by minute of day."""
    if frame.empty or "volume" not in frame:
        return {}
    regular = _regular_session(frame).copy()
    if regular.empty:
        return {}
    if current_session_date is None:
        current_session_date = regular.index[-1].date()
    historical = regular[regular.index.date != current_session_date].copy()
    if historical.empty:
        return {}
    cache_key = (symbol, historical.index[-1], len(historical))
    if cache_key in _PROFILE_CACHE:
        return _PROFILE_CACHE[cache_key]

    historical["session_date"] = historical.index.date
    historical["minute_of_day"] = _minute_of_day(historical.index)
    historical["cumulative_volume"] = historical.groupby("session_date")[
        "volume"
    ].cumsum()
    historical["five_minute_volume"] = (
        historical.groupby("session_date")["volume"]
        .rolling(5, min_periods=1)
        .sum()
        .reset_index(level=0, drop=True)
    )
    profile = (
        historical.groupby("minute_of_day")[["cumulative_volume", "five_minute_volume"]]
        .mean()
        .rename(
            columns={
                "cumulative_volume": "expected_volume",
                "five_minute_volume": "expected_5m_volume",
            }
        )
        .to_dict("index")
    )
    _PROFILE_CACHE[cache_key] = profile
    return profile


def volume_pace_metrics(symbol: str, frame: pd.DataFrame) -> VolumePaceMetrics:
    def unavailable(reason: str) -> VolumePaceMetrics:
        return VolumePaceMetrics(0, 0, 0, 0, 0, 0, False, "unavailable", reason)

    if frame.empty or "volume" not in frame:
        return unavailable("missing_historical_profile")

    latest = frame.index[-1]
    latest_local = (
        latest.tz_convert("America/New_York")
        if latest.tzinfo is not None
        else latest.tz_localize("America/New_York")
    )
    if not (MARKET_OPEN <= latest_local.time() < MARKET_CLOSE):
        return unavailable("outside_regular_session")

    regular = _regular_session(frame).copy()
    if regular.empty:
        return unavailable("outside_regular_session")
    current_date = latest_local.date()
    session = regular[regular.index.date == current_date].copy()
    if session.empty:
        return unavailable("outside_regular_session")
    profile = historical_volume_profile(symbol, regular, current_date)
    if not profile:
        return unavailable("missing_historical_profile")
    minute = int(_minute_of_day(pd.DatetimeIndex([session.index[-1]]))[0])
    expected = profile.get(minute)
    if not expected:
        return unavailable("minute_not_in_profile")
    current_volume = float(session["volume"].sum())
    recent_5m = float(session["volume"].tail(5).sum())
    expected_volume = float(expected.get("expected_volume") or 0)
    expected_5m = float(expected.get("expected_5m_volume") or 0)
    if expected_volume < MIN_EXPECTED_VOLUME or expected_5m < MIN_EXPECTED_VOLUME:
        return unavailable("minute_not_in_profile")
    vpr = current_volume / expected_volume
    accel = recent_5m / expected_5m
    passed = bool(vpr >= 1.2 and accel >= 1.2)
    return VolumePaceMetrics(
        current_volume,
        expected_volume,
        vpr,
        recent_5m,
        expected_5m,
        accel,
        passed,
        "available",
        None,
    )

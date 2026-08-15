from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time
from typing import Any
from zoneinfo import ZoneInfo

EASTERN_TIMEZONE = ZoneInfo("America/New_York")
PRE_MARKET_START = time(4, 0)
LIVE_MARKET_START = time(9, 30)
AFTER_HOURS_START = time(16, 0)
MARKET_CLOSED_START = time(20, 0)


@dataclass(frozen=True)
class MarketClock:
    """User-facing U.S. equity market clock in Eastern time."""

    now: datetime
    phase: str

    @property
    def time_text(self) -> str:
        return self.now.strftime("%-I:%M:%S %p %Z")

    @property
    def banner_text(self) -> str:
        return f"Market Time: {self.time_text} | {self.phase}"


def _coerce_datetime(value: Any) -> datetime | None:
    if value is None or isinstance(value, datetime):
        return value
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        if text.endswith("Z"):
            text = f"{text[:-1]}+00:00"
        try:
            return datetime.fromisoformat(text)
        except ValueError:
            return None
    return None


def eastern_time(value: datetime | str | None = None) -> datetime:
    """Return ``value`` converted to America/New_York, or current Eastern time."""
    coerced = _coerce_datetime(value)
    if coerced is None:
        return datetime.now(EASTERN_TIMEZONE)
    if coerced.tzinfo is None:
        coerced = coerced.replace(tzinfo=EASTERN_TIMEZONE)
    return coerced.astimezone(EASTERN_TIMEZONE)


def market_phase_at(value: datetime | None = None) -> str:
    """Return Walter's U.S. equity market phase from the shared Eastern clock.

    Weekends are always closed. Intraday phase labels are only meaningful on
    Monday through Friday; exchange holidays remain a separate calendar concern.
    """
    now = eastern_time(value)

    if now.weekday() >= 5:
        return "Market Closed"

    current_time = now.time()
    if PRE_MARKET_START <= current_time < LIVE_MARKET_START:
        return "Pre-Market"
    if LIVE_MARKET_START <= current_time < AFTER_HOURS_START:
        return "Live Market"
    if AFTER_HOURS_START <= current_time < MARKET_CLOSED_START:
        return "After-Hours"
    return "Market Closed"


def market_clock(value: datetime | None = None) -> MarketClock:
    """Build the single source of truth for displayed market time and phase."""
    now = eastern_time(value)
    return MarketClock(now=now, phase=market_phase_at(now))


def format_eastern_time(value: datetime | str | None, fallback: str = "not yet") -> str:
    """Format a user-facing timestamp in Eastern time with EDT/EST abbreviation."""
    if value is None or (isinstance(value, str) and not value.strip()):
        return fallback
    coerced = _coerce_datetime(value)
    if coerced is None:
        return fallback
    return eastern_time(coerced).strftime("%-I:%M:%S %p %Z")

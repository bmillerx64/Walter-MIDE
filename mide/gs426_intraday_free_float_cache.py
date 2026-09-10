"""GS426: stop repeating secondary free-float network refreshes every scan.

Sep. 10 Flight Recorder evidence showed the same low-float values repeating scan after
scan while Walter's live free-float resolver still recreated Yahoo Finance lookups for
all apparent low-float symbols on every pass. Free float is reference data, not a
per-minute market signal; FMP already treats successful values as trading-date cacheable
and transient failures with a short retry TTL.

GS426 applies the same principle to Walter's Yahoo secondary resolver used by the live
Webull Free-Float Gate: successful secondary values are process-cached for the current
New York trading date, transient failures are cached for ten minutes, and only cache
misses reach Yahoo. The existing conservative max(primary, secondary), outage handling,
float ceiling, and fail-closed semantics remain unchanged.

The cache is process-wide rather than provider-local so a Streamlit tab/session handoff
does not immediately repeat the same fundamentals calls. It contains only ticker,
floatShares/error class text already produced by the secondary provider and expires by
trading date / failure TTL. No discovery, market-data bars, VWAP, SuperTrend, scoring,
qualification, alerts, execution, or orders are changed.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from threading import Lock
from typing import Iterable
from zoneinfo import ZoneInfo

from .free_float import YahooFinanceFloatProvider as _BaseYahooFinanceFloatProvider


AUTHORITY = "REFERENCE_DATA_ACQUISITION_OPTIMIZATION_ONLY"
FAILURE_TTL = timedelta(minutes=10)
_CACHE_LOCK = Lock()
_CACHE: dict[tuple[str, str], dict] = {}
_INSTALL_GENERATION = object()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _trading_date(now: datetime | None = None) -> str:
    return (now or _now()).astimezone(ZoneInfo("America/New_York")).date().isoformat()


def _normalize(symbols: Iterable[str]) -> list[str]:
    return list(
        dict.fromkeys(
            str(symbol or "").strip().upper()
            for symbol in symbols
            if str(symbol or "").strip()
        )
    )


def _prune(date_key: str, now: datetime) -> None:
    expired = []
    for key, item in _CACHE.items():
        item_date, _symbol = key
        if item_date != date_key:
            expired.append(key)
            continue
        expires_at = item.get("expires_at")
        if expires_at is not None and expires_at <= now:
            expired.append(key)
    for key in expired:
        _CACHE.pop(key, None)


class IntradayCachedYahooFinanceFloatProvider(_BaseYahooFinanceFloatProvider):
    """Yahoo resolver with process-wide trading-date success and short failure cache."""

    def lookup_many(self, symbols: Iterable[str]):
        tickers = _normalize(symbols)
        now = _now()
        date_key = _trading_date(now)
        values: dict[str, float] = {}
        errors: dict[str, str] = {}
        misses: list[str] = []

        with _CACHE_LOCK:
            _prune(date_key, now)
            for ticker in tickers:
                cached = _CACHE.get((date_key, ticker))
                if cached is None:
                    misses.append(ticker)
                    continue
                value = cached.get("value")
                error = cached.get("error")
                if value is not None:
                    values[ticker] = float(value)
                elif error:
                    errors[ticker] = str(error)
                else:
                    misses.append(ticker)

        live_values: dict[str, float] = {}
        live_errors: dict[str, str] = {}
        if misses:
            live_values, live_errors = super().lookup_many(misses)
            with _CACHE_LOCK:
                for ticker in misses:
                    if ticker in live_values:
                        value = float(live_values[ticker])
                        _CACHE[(date_key, ticker)] = {
                            "value": value,
                            "error": None,
                            "expires_at": None,
                        }
                        values[ticker] = value
                    else:
                        error = str(live_errors.get(ticker) or "floatShares unresolved")
                        _CACHE[(date_key, ticker)] = {
                            "value": None,
                            "error": error,
                            "expires_at": now + FAILURE_TTL,
                        }
                        errors[ticker] = error

        self.walter_gs426_cache_diagnostics = {
            "authority": AUTHORITY,
            "requested": len(tickers),
            "cache_hits": len(tickers) - len(misses),
            "network_misses": len(misses),
            "successes": len(values),
            "errors": len(errors),
            "trading_date": date_key,
            "failure_ttl_seconds": int(FAILURE_TTL.total_seconds()),
            "trading_logic_changed": False,
        }
        return values, errors


def install() -> None:
    """Patch only the Yahoo resolver alias used by live Webull free-float enrichment."""
    from . import free_float_inspector

    current = free_float_inspector.YahooFinanceFloatProvider
    if getattr(current, "_gs426_install_generation", None) is _INSTALL_GENERATION:
        return
    IntradayCachedYahooFinanceFloatProvider._gs426_intraday_cache = True
    IntradayCachedYahooFinanceFloatProvider._gs426_install_generation = _INSTALL_GENERATION
    IntradayCachedYahooFinanceFloatProvider._gs426_original = current
    free_float_inspector.YahooFinanceFloatProvider = IntradayCachedYahooFinanceFloatProvider

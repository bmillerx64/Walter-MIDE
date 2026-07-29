"""Free-float reference data from Financial Modeling Prep.

Alpaca stock snapshots contain market data (trades, quotes, and bars), not
company share-structure fundamentals. Stage 2 therefore obtains float shares
from FMP's dedicated shares-float endpoint and attaches it to the snapshot's
reference data before applying the identity gate.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
import logging
import os
from pathlib import Path
import sqlite3
from threading import Lock
from typing import Iterable, Protocol
from zoneinfo import ZoneInfo

import requests


logger = logging.getLogger(__name__)


class FreeFloatProvider(Protocol):
    """Provider contract shared by free-float enrichment and diagnostics."""

    provider_name: str

    def lookup_many(
        self, symbols: Iterable[str]
    ) -> tuple[dict[str, float], dict[str, str]]: ...


@dataclass(frozen=True)
class FreeFloatCacheDiagnostics:
    """Read-only snapshot of the persistent FMP cache and request counters."""

    cache_hits: int
    cache_misses: int
    cached_symbols: int
    requests_made: int
    requests_avoided: int
    oldest_entry: str | None
    newest_entry: str | None


def cache_diagnostics_or_default(provider: object) -> FreeFloatCacheDiagnostics:
    """Return provider diagnostics, or an empty snapshot when unavailable.

    Diagnostics are optional observability data and must never prevent Walter
    from starting or rendering its Diagnostics page.  Keeping this fallback
    outside the scanner also lets the UI tolerate an older or alternate
    provider which does not implement ``cache_diagnostics``.
    """
    empty = FreeFloatCacheDiagnostics(0, 0, 0, 0, 0, None, None)
    diagnostics = getattr(provider, "cache_diagnostics", None)
    if not callable(diagnostics):
        logger.warning("Free-float cache diagnostics are unavailable")
        return empty
    try:
        return diagnostics()
    except Exception:
        logger.warning("Unable to read free-float cache diagnostics", exc_info=True)
        return empty


class FreeFloatClient:
    """FMP adapter backed by a daily, persistent SQLite cache.

    Successful values are scoped to the New York trading date and live for at
    most 24 hours.  Failures have a much shorter lifetime so a transient FMP
    outage cannot turn every scan into another request storm.
    """

    BASE_URL = "https://financialmodelingprep.com/stable"
    provider_name = "Financial Modeling Prep"

    def __init__(
        self,
        api_key: str,
        timeout: int = 12,
        max_workers: int = 8,
        *,
        cache_path: str | Path | None = None,
        cache_ttl: timedelta = timedelta(hours=24),
        failure_ttl: timedelta = timedelta(minutes=10),
        preload_bulk: bool | None = None,
    ):
        self.api_key = str(api_key or "").strip()
        self.timeout = timeout
        self.max_workers = max(1, int(max_workers))
        default_path = Path.home() / ".cache" / "walter-mide" / "fmp-float.sqlite3"
        self.cache_path = Path(
            cache_path or os.getenv("FMP_FLOAT_CACHE_PATH") or default_path
        )
        self.cache_ttl = cache_ttl
        self.failure_ttl = failure_ttl
        self.preload_bulk = (
            str(os.getenv("FMP_FLOAT_BULK_PRELOAD", "")).lower() in {"1", "true", "yes"}
            if preload_bulk is None else bool(preload_bulk)
        )
        self.requests_made = 0
        self.cache_hits = 0
        self.cache_misses = 0
        self.cache_age_seconds: float | None = None
        self._cache_lock = Lock()

    @property
    def requests_avoided(self) -> int:
        """Return cache-served lookups using the legacy diagnostic name.

        An avoided FMP request is not a separate event: every fresh cache hit
        avoids exactly one per-symbol request. Deriving the value prevents the
        two labels from reporting contradictory counts.
        """
        return self.cache_hits

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    def _trading_date(self, now: datetime | None = None) -> date:
        return (now or self._now()).astimezone(ZoneInfo("America/New_York")).date()

    def _connect(self) -> sqlite3.Connection:
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.cache_path, timeout=15)
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute(
            """CREATE TABLE IF NOT EXISTS float_cache (
                ticker TEXT NOT NULL, trading_date TEXT NOT NULL,
                float_shares REAL, error TEXT, retrieved_at TEXT NOT NULL,
                PRIMARY KEY (ticker, trading_date)
            )"""
        )
        return connection

    def _store(self, rows: Iterable[tuple[str, float | None, str | None]], now: datetime) -> None:
        try:
            with self._cache_lock, self._connect() as connection:
                connection.executemany(
                    "INSERT OR REPLACE INTO float_cache VALUES (?, ?, ?, ?, ?)",
                    ((ticker, self._trading_date(now).isoformat(), shares, error,
                      now.isoformat()) for ticker, shares, error in rows),
                )
                # Old dates are never read; bound disk growth without affecting today.
                connection.execute(
                    "DELETE FROM float_cache WHERE retrieved_at < ?",
                    ((now - timedelta(days=7)).isoformat(),),
                )
        except (OSError, sqlite3.Error):
            logger.warning("Unable to persist FMP float cache", exc_info=True)

    def _cached_values(self, tickers: list[str]) -> tuple[dict[str, float], list[str]]:
        now = self._now()
        values: dict[str, float] = {}
        missing: list[str] = []
        self._cached_errors: dict[str, str] = {}
        try:
            with self._connect() as connection:
                rows = {
                    row[0]: row[1:]
                    for row in connection.execute(
                        "SELECT ticker, float_shares, error, retrieved_at FROM float_cache "
                        "WHERE trading_date = ?", (self._trading_date(now).isoformat(),)
                    )
                }
        except (OSError, sqlite3.Error):
            rows = {}
        ages = []
        hits = 0
        for ticker in tickers:
            row = rows.get(ticker)
            if row:
                shares, error, timestamp = row
                try:
                    age = now - datetime.fromisoformat(timestamp).astimezone(timezone.utc)
                    ttl = self.failure_ttl if error else self.cache_ttl
                    if age < ttl:
                        ages.append(age.total_seconds())
                        hits += 1
                        if error:
                            self._cached_errors[ticker] = error
                        elif shares and shares > 0:
                            values[ticker] = float(shares)
                        continue
                except (TypeError, ValueError):
                    pass
            missing.append(ticker)
        # A fresh cached failure is also a served lookup: it prevents another
        # provider request just as a cached float does.
        self.cache_hits += hits
        self.cache_misses += len(missing)
        self.cache_age_seconds = max(ages) if ages else None
        return values, missing

    def _reset_scan_diagnostics(self) -> None:
        """Reset per-scan counters once, before any cache lookup occurs."""
        self.requests_made = 0
        self.cache_hits = 0
        self.cache_misses = 0
        self.cache_age_seconds = None

    def cache_diagnostics(self) -> FreeFloatCacheDiagnostics:
        """Return cache inventory without changing cache counters or fetching data."""
        cached_symbols = 0
        oldest_entry = None
        newest_entry = None
        try:
            with self._connect() as connection:
                row = connection.execute(
                    "SELECT COUNT(DISTINCT ticker), MIN(retrieved_at), MAX(retrieved_at) "
                    "FROM float_cache WHERE trading_date = ?",
                    (self._trading_date().isoformat(),),
                ).fetchone()
            if row:
                cached_symbols = int(row[0] or 0)
                oldest_entry = row[1]
                newest_entry = row[2]
        except (OSError, sqlite3.Error):
            logger.warning("Unable to inspect FMP float cache", exc_info=True)
        return FreeFloatCacheDiagnostics(
            cache_hits=self.cache_hits,
            cache_misses=self.cache_misses,
            cached_symbols=cached_symbols,
            requests_made=self.requests_made,
            requests_avoided=self.requests_avoided,
            oldest_entry=oldest_entry,
            newest_entry=newest_entry,
        )

    def _lookup(self, symbol: str) -> tuple[str, float | None, str | None]:
        ticker = str(symbol).strip().upper()
        url = f"{self.BASE_URL}/shares-float"
        try:
            with self._cache_lock:
                self.requests_made += 1
            logger.info(
                "FMP request: url=%s ticker=%s FMP_API_KEY_found=%s",
                url,
                ticker,
                bool(self.api_key),
            )
            response = requests.get(
                url,
                params={"symbol": ticker, "apikey": self.api_key},
                timeout=self.timeout,
            )
            response.raise_for_status()
            payload = response.json()
            row = payload[0] if isinstance(payload, list) and payload else payload
            value = row.get("floatShares") if isinstance(row, dict) else None
            shares = float(value) if value is not None else None
            if shares is None or shares <= 0:
                return ticker, None, "response contained no positive floatShares"
            return ticker, shares, None
        except Exception as exc:
            return ticker, None, str(exc)

    def lookup_many(self, symbols: Iterable[str]) -> tuple[dict[str, float], dict[str, str]]:
        """Return successful float-share values and per-symbol lookup errors."""
        # Diagnostics describe this scan, rather than the lifetime of this object.
        self._reset_scan_diagnostics()
        tickers = list(
            dict.fromkeys(
                str(symbol or "").strip().upper() for symbol in symbols if symbol
            )
        )
        values, uncached = self._cached_values(tickers)
        errors: dict[str, str] = dict(self._cached_errors)
        if self.preload_bulk and uncached and self.api_key:
            self.preload_all()
            values, uncached = self._cached_values(tickers)
            errors.update(self._cached_errors)
        if not self.api_key or not uncached:
            self._log_diagnostics()
            return values, errors
        with ThreadPoolExecutor(max_workers=min(self.max_workers, len(uncached))) as pool:
            futures = {pool.submit(self._lookup, ticker): ticker for ticker in uncached}
            for future in as_completed(futures):
                ticker, shares, error = future.result()
                if shares is not None:
                    values[ticker] = shares
                elif error:
                    errors[ticker] = error
        self._store(
            ((ticker, values.get(ticker), errors.get(ticker)) for ticker in uncached),
            self._now(),
        )
        self._log_diagnostics()
        return values, errors

    def preload_all(self) -> int:
        """Optionally populate today's cache with FMP's bulk float universe."""
        url = f"{self.BASE_URL}/shares-float-all"
        try:
            with self._cache_lock:
                self.requests_made += 1
            response = requests.get(url, params={"apikey": self.api_key}, timeout=self.timeout)
            response.raise_for_status()
            payload = response.json()
            rows = []
            for item in payload if isinstance(payload, list) else []:
                ticker = str(item.get("symbol") or "").strip().upper()
                shares = item.get("floatShares")
                if ticker and shares is not None and float(shares) > 0:
                    rows.append((ticker, float(shares), None))
            self._store(rows, self._now())
            return len(rows)
        except Exception as exc:
            logger.warning("FMP bulk float preload failed: %s", exc)
            return 0

    def _log_diagnostics(self) -> None:
        logger.info(
            "FMP float cache: hits=%d misses=%d requests_made=%d "
            "requests_avoided=%d cache_age_seconds=%s",
            self.cache_hits, self.cache_misses, self.requests_made,
            self.requests_avoided,
            "n/a" if self.cache_age_seconds is None else f"{self.cache_age_seconds:.1f}",
        )


def enrich_snapshots_with_free_float(
    snapshots: dict[str, dict], provider: FreeFloatProvider
) -> tuple[int, dict[str, str]]:
    """Attach FMP float shares only where a snapshot does not already have it."""
    field_names = ("float_shares", "shares_float", "free_float", "float_millions")
    missing = []
    for symbol, snapshot in snapshots.items():
        reference = snapshot.get("reference") or {}
        if not any(
            snapshot.get(key) is not None or reference.get(key) is not None
            for key in field_names
        ):
            missing.append(symbol)

    values, errors = provider.lookup_many(missing)
    for symbol, shares in values.items():
        snapshot = snapshots.get(symbol)
        if snapshot is None:
            continue
        reference = snapshot.get("reference")
        if not isinstance(reference, dict):
            reference = {}
            snapshot["reference"] = reference
        reference["float_shares"] = shares
        reference["provider"] = "Financial Modeling Prep"
    return len(values), errors


class YahooFinanceFloatProvider:
    """Fetch Yahoo Finance's ``defaultKeyStatistics.floatShares`` value.

    Alpaca stock snapshots are a market-data response (trades, quotes and bars),
    not a fundamentals response. Keeping this adapter separate prevents us from
    pretending a missing field in a successful Alpaca snapshot is a failed
    snapshot request.
    """

    BASE_URL = "https://query2.finance.yahoo.com"
    COOKIE_URL = "https://fc.yahoo.com"
    provider_name = "Yahoo Finance defaultKeyStatistics"

    def __init__(self, timeout: int = 12, max_workers: int = 8):
        self.timeout = timeout
        self.max_workers = max_workers
        self.session = requests.Session()
        self.session.headers.update(
            {"User-Agent": "Mozilla/5.0 (Walter-MIDE free-float lookup)"}
        )
        self._crumb: str | None = None
        self._crumb_lock = Lock()

    def _get_crumb(self) -> str:
        """Establish Yahoo's cookie and CSRF crumb once for the whole batch."""
        if self._crumb:
            return self._crumb
        with self._crumb_lock:
            if self._crumb:
                return self._crumb
            # Yahoo's cookie bootstrap URL commonly returns a non-2xx landing
            # response while still setting the session cookie, so only the
            # subsequent crumb response determines whether setup succeeded.
            self.session.get(self.COOKIE_URL, timeout=self.timeout)
            crumb_response = self.session.get(
                f"{self.BASE_URL}/v1/test/getcrumb", timeout=self.timeout
            )
            crumb_response.raise_for_status()
            crumb = crumb_response.text.strip()
            if not crumb:
                raise ValueError("Yahoo Finance returned an empty request crumb")
            self._crumb = crumb
            return crumb

    @staticmethod
    def parse(payload: object) -> float | None:
        """Parse the documented quote-summary envelope and its ``raw`` value."""
        if not isinstance(payload, dict):
            return None
        summary = payload.get("quoteSummary")
        results = summary.get("result") if isinstance(summary, dict) else None
        statistics = results[0].get("defaultKeyStatistics") if results else None
        value = statistics.get("floatShares") if isinstance(statistics, dict) else None
        if isinstance(value, dict):
            value = value.get("raw")
        try:
            shares = float(value)
        except (TypeError, ValueError):
            return None
        return shares if shares > 0 else None

    def lookup(self, symbol: str) -> float | None:
        ticker = str(symbol or "").strip().upper()
        response = self.session.get(
            f"{self.BASE_URL}/v10/finance/quoteSummary/{ticker}",
            params={
                "modules": "defaultKeyStatistics",
                "crumb": self._get_crumb(),
            },
            timeout=self.timeout,
        )
        response.raise_for_status()
        return self.parse(response.json())

    def lookup_many(self, symbols: Iterable[str]) -> tuple[dict[str, float], dict[str, str]]:
        """Look up symbols concurrently; one provider error cannot abort a scan."""
        tickers = list(dict.fromkeys(str(s).strip().upper() for s in symbols if s))
        values: dict[str, float] = {}
        errors: dict[str, str] = {}
        with ThreadPoolExecutor(max_workers=min(self.max_workers, len(tickers) or 1)) as pool:
            futures = {pool.submit(self.lookup, ticker): ticker for ticker in tickers}
            for future in as_completed(futures):
                ticker = futures[future]
                try:
                    value = future.result()
                    if value is not None:
                        values[ticker] = value
                    else:
                        errors[ticker] = "floatShares missing from quote summary"
                except Exception as exc:
                    errors[ticker] = f"{type(exc).__name__}: {exc}"
        return values, errors

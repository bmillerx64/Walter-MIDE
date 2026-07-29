"""Free-float reference data from Financial Modeling Prep.

Alpaca stock snapshots contain market data (trades, quotes, and bars), not
company share-structure fundamentals. Stage 2 therefore obtains float shares
from FMP's dedicated shares-float endpoint and attaches it to the snapshot's
reference data before applying the identity gate.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
import json
import logging
import os
from pathlib import Path
from threading import Lock
from typing import Iterable, Protocol

import requests


logger = logging.getLogger(__name__)


class FreeFloatProvider(Protocol):
    """Provider contract shared by free-float enrichment and diagnostics."""

    provider_name: str

    def lookup_many(
        self, symbols: Iterable[str]
    ) -> tuple[dict[str, float], dict[str, str]]: ...


class FreeFloatClient:
    """Small adapter for FMP's stable Shares Float endpoint."""

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
        cache_max_entries: int = 512,
    ):
        self.api_key = str(api_key or "").strip()
        self.timeout = timeout
        self.max_workers = max(1, int(max_workers))
        default_path = Path.home() / ".cache" / "walter-mide" / "fmp-float.json"
        self.cache_path = Path(
            cache_path or os.getenv("FMP_FLOAT_CACHE_PATH") or default_path
        )
        self.cache_ttl = cache_ttl
        self.cache_max_entries = max(1, int(cache_max_entries))
        self.requests_made = 0
        self.cache_hits = 0
        self._cache_lock = Lock()

    def _read_cache(self) -> dict[str, dict]:
        try:
            payload = json.loads(self.cache_path.read_text())
            if not isinstance(payload, dict):
                return {}
        except (OSError, ValueError):
            return {}

        # A rotating discovery universe previously made this dictionary grow
        # forever.  Every client then materialized the complete JSON object for
        # every scan.  Keep only the newest useful entries; the cache is an
        # optimization and must not become runtime history.
        now = datetime.now(timezone.utc)
        retained: list[tuple[datetime, str, dict]] = []
        for ticker, entry in payload.items():
            try:
                retrieved_at = datetime.fromisoformat(str(entry["retrieved_at"]))
                retrieved_at = retrieved_at.astimezone(timezone.utc)
                shares = float(entry["float_shares"])
            except (AttributeError, KeyError, TypeError, ValueError):
                continue
            if shares > 0 and now - retrieved_at < self.cache_ttl:
                retained.append((retrieved_at, ticker, entry))
        retained.sort(reverse=True)
        cache = {
            ticker: entry
            for _, ticker, entry in retained[: self.cache_max_entries]
        }
        if len(cache) != len(payload):
            self._write_cache(cache)
        return cache

    def _write_cache(self, cache: dict[str, dict]) -> None:
        """Persist successful lookups atomically; cache failure never stops a scan."""
        try:
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.cache_path.with_suffix(self.cache_path.suffix + ".tmp")
            temporary.write_text(json.dumps(cache, sort_keys=True))
            temporary.replace(self.cache_path)
        except OSError:
            return

    def _cached_values(self, tickers: list[str]) -> tuple[dict[str, float], list[str]]:
        now = datetime.now(timezone.utc)
        cache = self._read_cache()
        values: dict[str, float] = {}
        missing: list[str] = []
        for ticker in tickers:
            entry = cache.get(ticker) or {}
            try:
                retrieved_at = datetime.fromisoformat(str(entry["retrieved_at"]))
                shares = float(entry["float_shares"])
                fresh = now - retrieved_at.astimezone(timezone.utc) < self.cache_ttl
            except (KeyError, TypeError, ValueError):
                fresh = False
                shares = 0
            if fresh and shares > 0:
                values[ticker] = shares
            else:
                missing.append(ticker)
        self.cache_hits = len(values)
        return values, missing

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
        tickers = list(
            dict.fromkeys(
                str(symbol or "").strip().upper() for symbol in symbols if symbol
            )
        )
        values, uncached = self._cached_values(tickers)
        errors: dict[str, str] = {}
        if not self.api_key or not uncached:
            return values, errors
        with ThreadPoolExecutor(max_workers=min(self.max_workers, len(uncached))) as pool:
            futures = {pool.submit(self._lookup, ticker): ticker for ticker in uncached}
            for future in as_completed(futures):
                ticker, shares, error = future.result()
                if shares is not None:
                    values[ticker] = shares
                elif error:
                    errors[ticker] = error
        if values:
            cache = self._read_cache()
            retrieved_at = datetime.now(timezone.utc).isoformat()
            for ticker in uncached:
                if ticker in values:
                    cache[ticker] = {
                        "float_shares": values[ticker],
                        "retrieved_at": retrieved_at,
                    }
            if len(cache) > self.cache_max_entries:
                cache = dict(
                    sorted(
                        cache.items(),
                        key=lambda item: item[1].get("retrieved_at", ""),
                        reverse=True,
                    )[: self.cache_max_entries]
                )
            self._write_cache(cache)
        return values, errors


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

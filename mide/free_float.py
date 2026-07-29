"""Free-float reference data from Financial Modeling Prep.

Alpaca stock snapshots contain market data (trades, quotes, and bars), not
company share-structure fundamentals. Stage 2 therefore obtains float shares
from FMP's dedicated shares-float endpoint and attaches it to the snapshot's
reference data before applying the identity gate.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Iterable

import requests


class FreeFloatClient:
    """Small adapter for FMP's stable Shares Float endpoint."""

    BASE_URL = "https://financialmodelingprep.com/stable"

    def __init__(self, api_key: str, timeout: int = 12, max_workers: int = 8):
        self.api_key = str(api_key or "").strip()
        self.timeout = timeout
        self.max_workers = max(1, int(max_workers))

    def _lookup(self, symbol: str) -> tuple[str, float | None, str | None]:
        ticker = str(symbol).strip().upper()
        try:
            response = requests.get(
                f"{self.BASE_URL}/shares-float",
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
        values: dict[str, float] = {}
        errors: dict[str, str] = {}
        if not self.api_key or not tickers:
            return values, errors
        with ThreadPoolExecutor(max_workers=min(self.max_workers, len(tickers))) as pool:
            futures = {pool.submit(self._lookup, ticker): ticker for ticker in tickers}
            for future in as_completed(futures):
                ticker, shares, error = future.result()
                if shares is not None:
                    values[ticker] = shares
                elif error:
                    errors[ticker] = error
        return values, errors


def enrich_snapshots_with_free_float(
    snapshots: dict[str, dict], provider: FreeFloatClient
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
    provider_name = "Yahoo Finance defaultKeyStatistics"

    def __init__(self, timeout: int = 12, max_workers: int = 8):
        self.timeout = timeout
        self.max_workers = max_workers

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
        response = requests.get(
            f"{self.BASE_URL}/v10/finance/quoteSummary/{ticker}",
            params={"modules": "defaultKeyStatistics"},
            headers={"User-Agent": "Mozilla/5.0 (Walter-MIDE free-float lookup)"},
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

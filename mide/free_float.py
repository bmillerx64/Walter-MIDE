"""Free-float reference data independent of Alpaca's market snapshots."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Iterable

import requests


class YahooFinanceFloatProvider:
    """Fetch Yahoo Finance's ``defaultKeyStatistics.floatShares`` value.

    Alpaca stock snapshots are a market-data response (trades, quotes and bars),
    not a fundamentals response.  Keeping this adapter separate prevents us from
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

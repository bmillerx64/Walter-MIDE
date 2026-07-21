from __future__ import annotations
from datetime import datetime, timezone
from typing import Iterable
import requests
import pandas as pd


class AlpacaError(RuntimeError):
    pass


class AlpacaClient:
    DATA = "https://data.alpaca.markets"
    TRADING = "https://paper-api.alpaca.markets"
    NEWS_MAX_LIMIT = 50
    SCREENER_MAX_LIMIT = 50
    BARS_MAX_LIMIT = 10_000

    def __init__(self, api_key: str, secret_key: str, feed: str = "iex", timeout: int = 20):
        self.feed = (feed or "iex").lower()
        self.timeout = timeout
        self.warnings: list[str] = []
        self.headers = {
            "APCA-API-KEY-ID": api_key,
            "APCA-API-SECRET-KEY": secret_key,
        }

    def _get(self, base: str, path: str, params=None):
        response = requests.get(
            base + path, headers=self.headers, params=params or {}, timeout=self.timeout
        )
        if response.status_code >= 400:
            raise AlpacaError(f"{response.status_code}: {response.text[:400]}")
        return response.json()

    def assets(self):
    params = {"status": "active", "asset_class": "us_equity"}
    last_error = None

    for base in (
        "https://paper-api.alpaca.markets",
        "https://api.alpaca.markets",
    ):
        try:
            data = self._get(base, "/v2/assets", params)
            return [
                item for item in data
                if item.get("tradable")
                and item.get("status") == "active"
                and item.get("class") == "us_equity"
                and not item.get("symbol", "").endswith((".W", ".U", ".R"))
            ]
        except Exception as exc:
            last_error = exc

    raise AlpacaError(f"Assets unavailable on paper and live endpoints: {last_error}")

    def movers(self, top: int = 50):
        try:
            payload = self._get(
                self.DATA, "/v1beta1/screener/stocks/movers",
                {"top": max(1, min(int(top), self.SCREENER_MAX_LIMIT))}
            )
            return payload.get("gainers", []) + payload.get("losers", [])
        except AlpacaError as exc:
            self.warnings.append(f"Movers unavailable: {exc}")
            return []

    def most_actives(self, top: int = 100):
        try:
            payload = self._get(
                self.DATA, "/v1beta1/screener/stocks/most-actives",
                {"top": max(1, min(int(top), self.SCREENER_MAX_LIMIT)), "by": "volume"}
            )
            return payload.get("most_actives", [])
        except AlpacaError as exc:
            self.warnings.append(f"Most-actives unavailable: {exc}")
            return []

    def news(self, start: datetime, limit: int = 200):
        """Fetch up to `limit` news items while respecting Alpaca's 50-item page cap."""
        wanted = max(0, int(limit))
        if wanted == 0:
            return []
        items: list[dict] = []
        page_token = None
        while len(items) < wanted:
            params = {
                "start": start.astimezone(timezone.utc).isoformat(),
                "limit": min(self.NEWS_MAX_LIMIT, wanted - len(items)),
                "sort": "desc",
                "include_content": "false",
            }
            if page_token:
                params["page_token"] = page_token
            payload = self._get(self.DATA, "/v1beta1/news", params)
            page = payload.get("news", []) or []
            items.extend(page)
            page_token = payload.get("next_page_token")
            if not page_token or not page:
                break
        return items[:wanted]

    def snapshots(self, symbols: Iterable[str]):
        """Fetch snapshots without allowing one malformed symbol to abort a scan.

        Alpaca rejects the entire request when even one symbol is invalid.  We first
        try the batch, then recursively split a failed batch until the bad symbol is
        isolated and skipped.
        """
        cleaned = []
        for raw in symbols:
            symbol = str(raw or "").strip().upper()
            if not symbol or ":" in symbol:
                if symbol:
                    self.warnings.append(f"Skipped non-U.S./malformed snapshot symbol {symbol}")
                continue
            if symbol not in cleaned:
                cleaned.append(symbol)
        symbols = cleaned
        if not symbols:
            return {}
        try:
            return self._get(
                self.DATA, "/v2/stocks/snapshots",
                {"symbols": ",".join(symbols), "feed": self.feed},
            )
        except AlpacaError as exc:
            if len(symbols) == 1:
                self.warnings.append(f"Skipped invalid/unavailable symbol {symbols[0]}: {exc}")
                return {}
            midpoint = len(symbols) // 2
            left = self.snapshots(symbols[:midpoint])
            right = self.snapshots(symbols[midpoint:])
            return {**left, **right}

    def bars(self, symbols: Iterable[str], start: datetime, timeframe="1Min", limit=10000):
        """Fetch multi-symbol bars without allowing one bad ticker to kill the scan.

        Alpaca rejects an entire bars request if even one symbol is unsupported.
        We first remove obviously non-U.S./malformed symbols, then try the batch.
        If Alpaca still rejects it, the batch is recursively split until the bad
        symbol is isolated, logged, and skipped. Valid symbols continue normally.
        """
        cleaned = []
        for raw in symbols:
            symbol = str(raw or "").strip().upper()
            if not symbol or ":" in symbol:
                if symbol:
                    self.warnings.append(f"Skipped non-U.S./malformed bars symbol {symbol}")
                continue
            if symbol not in cleaned:
                cleaned.append(symbol)
        if not cleaned:
            return {}

        per_page = max(1, min(int(limit), self.BARS_MAX_LIMIT))

        def fetch_batch(batch: list[str]) -> dict[str, list]:
            combined: dict[str, list] = {symbol: [] for symbol in batch}
            page_token = None
            try:
                while True:
                    params = {
                        "symbols": ",".join(batch),
                        "timeframe": timeframe,
                        "start": start.astimezone(timezone.utc).isoformat(),
                        "limit": per_page,
                        "adjustment": "raw",
                        "feed": self.feed,
                        "sort": "asc",
                    }
                    if page_token:
                        params["page_token"] = page_token
                    payload = self._get(self.DATA, "/v2/stocks/bars", params)
                    for symbol, rows in (payload.get("bars", {}) or {}).items():
                        combined.setdefault(symbol, []).extend(rows or [])
                    page_token = payload.get("next_page_token")
                    if not page_token:
                        return combined
            except AlpacaError as exc:
                if len(batch) == 1:
                    self.warnings.append(f"Skipped invalid/unavailable bars symbol {batch[0]}: {exc}")
                    return {}
                midpoint = len(batch) // 2
                left = fetch_batch(batch[:midpoint])
                right = fetch_batch(batch[midpoint:])
                return {**left, **right}

        return fetch_batch(cleaned)

    @staticmethod
    def bars_frame(items):
        if not items:
            return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
        frame = pd.DataFrame(items).rename(columns={
            "t": "timestamp", "o": "open", "h": "high", "l": "low", "c": "close", "v": "volume"
        })
        frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True)
        return frame.set_index("timestamp")[["open", "high", "low", "close", "volume"]].sort_index()

from __future__ import annotations
from datetime import datetime, timezone
from typing import Iterable
import csv
import io
import requests
import pandas as pd


class AlpacaError(RuntimeError):
    pass


class AlpacaClient:
    DATA = "https://data.alpaca.markets"
    PAPER_TRADING = "https://paper-api.alpaca.markets"
    LIVE_TRADING = "https://api.alpaca.markets"
    NEWS_MAX_LIMIT = 50
    SCREENER_MAX_LIMIT = 50
    BARS_MAX_LIMIT = 10_000

    @classmethod
    def _request_limit(cls, requested: int, maximum: int) -> int:
        """Clamp Alpaca request sizes to the endpoint-supported range."""
        return max(1, min(int(requested), maximum))

    def __init__(self, api_key: str, secret_key: str, feed: str = "iex", timeout: int = 20):
        self.feed = (feed or "iex").lower()
        self.timeout = timeout
        self.warnings: list[str] = []
        self.diagnostics: dict[str, object] = {}
        self.headers = {
            "APCA-API-KEY-ID": api_key.strip(),
            "APCA-API-SECRET-KEY": secret_key.strip(),
        }

    def _get(self, base: str, path: str, params=None, *, authenticated: bool = True):
        response = requests.get(
            base + path,
            headers=self.headers if authenticated else {},
            params=params or {},
            timeout=self.timeout,
        )
        if response.status_code >= 400:
            body = response.text[:400].replace("\n", " ")
            raise AlpacaError(f"{response.status_code} from {path}: {body}")
        try:
            return response.json()
        except ValueError as exc:
            raise AlpacaError(f"Invalid JSON from {path}: {exc}") from exc

    def credential_status(self) -> str:
        """Identify which Alpaca trading environment accepts the configured keys."""
        return credential_status(self)

    def assets(self):
        """Return active tradable U.S. equities from whichever Alpaca environment accepts the keys."""
        params = {"status": "active", "asset_class": "us_equity"}
        errors = []
        for label, base in (("paper", self.PAPER_TRADING), ("live", self.LIVE_TRADING)):
            try:
                data = self._get(base, "/v2/assets", params)
                if not isinstance(data, list):
                    raise AlpacaError(f"Unexpected assets response type: {type(data).__name__}")
                filtered = []
                for item in data:
                    symbol = str(item.get("symbol") or "").strip().upper()
                    asset_class = item.get("class") or item.get("asset_class")
                    if not symbol or not item.get("tradable") or item.get("status") != "active":
                        continue
                    if asset_class and asset_class != "us_equity":
                        continue
                    if symbol.endswith((".W", ".U", ".R")):
                        continue
                    filtered.append(item)
                self.diagnostics["assets_endpoint"] = label
                self.diagnostics["assets_raw"] = len(data)
                self.diagnostics["assets_eligible"] = len(filtered)
                if filtered:
                    return filtered
                errors.append(f"{label}: endpoint returned {len(data)} assets but 0 eligible")
            except Exception as exc:
                errors.append(f"{label}: {exc}")
        raise AlpacaError("Assets unavailable (" + " | ".join(errors) + ")")

    def public_symbol_fallback(self) -> list[str]:
        """Unauthenticated fallback universe from Nasdaq Trader symbol directories."""
        urls = (
            "https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqlisted.txt",
            "https://www.nasdaqtrader.com/dynamic/SymDir/otherlisted.txt",
        )
        symbols: set[str] = set()
        errors = []
        for url in urls:
            try:
                response = requests.get(url, timeout=self.timeout)
                response.raise_for_status()
                rows = csv.DictReader(io.StringIO(response.text), delimiter="|")
                for row in rows:
                    raw = row.get("Symbol") or row.get("ACT Symbol") or ""
                    symbol = raw.strip().upper()
                    if symbol and symbol not in {"FILE CREATION TIME"} and not symbol.endswith(("W", "U", "R")):
                        symbols.add(symbol)
            except Exception as exc:
                errors.append(str(exc))
        self.diagnostics["public_fallback_symbols"] = len(symbols)
        if not symbols:
            raise AlpacaError("Public symbol fallback unavailable: " + " | ".join(errors))
        return sorted(symbols)

    def movers(self, top: int = 50):
        try:
            payload = self._get(
                self.DATA, "/v1beta1/screener/stocks/movers",
                {"top": self._request_limit(top, self.SCREENER_MAX_LIMIT)},
            )
            items = (payload.get("gainers", []) or []) + (payload.get("losers", []) or [])
            self.diagnostics["movers"] = len(items)
            return items
        except Exception as exc:
            self.diagnostics["movers"] = 0
            self.warnings.append(f"Movers unavailable: {exc}")
            return []

    def most_actives(self, top: int = 100):
        try:
            payload = self._get(
                self.DATA, "/v1beta1/screener/stocks/most-actives",
                {"top": self._request_limit(top, self.SCREENER_MAX_LIMIT), "by": "volume"},
            )
            items = payload.get("most_actives", []) or []
            self.diagnostics["most_actives"] = len(items)
            return items
        except Exception as exc:
            self.diagnostics["most_actives"] = 0
            self.warnings.append(f"Most-actives unavailable: {exc}")
            return []

    def news(self, start: datetime, limit: int = 200):
        wanted = max(0, int(limit))
        if wanted == 0:
            return []
        items: list[dict] = []
        page_token = None
        while len(items) < wanted:
            params = {
                "start": start.astimezone(timezone.utc).isoformat(),
                "limit": self._request_limit(wanted - len(items), self.NEWS_MAX_LIMIT),
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
        self.diagnostics["news_items"] = len(items[:wanted])
        return items[:wanted]

    def snapshots(self, symbols: Iterable[str]):
        cleaned = []
        for raw in symbols:
            symbol = str(raw or "").strip().upper()
            if not symbol or ":" in symbol:
                continue
            if symbol not in cleaned:
                cleaned.append(symbol)
        if not cleaned:
            return {}
        try:
            return self._get(
                self.DATA, "/v2/stocks/snapshots",
                {"symbols": ",".join(cleaned), "feed": self.feed},
            )
        except AlpacaError as exc:
            if len(cleaned) == 1:
                self.warnings.append(f"Skipped snapshot symbol {cleaned[0]}: {exc}")
                return {}
            midpoint = len(cleaned) // 2
            return {**self.snapshots(cleaned[:midpoint]), **self.snapshots(cleaned[midpoint:])}

    def bars(self, symbols: Iterable[str], start: datetime, timeframe="1Min", limit=10000):
        cleaned = []
        for raw in symbols:
            symbol = str(raw or "").strip().upper()
            if symbol and ":" not in symbol and symbol not in cleaned:
                cleaned.append(symbol)
        if not cleaned:
            return {}
        per_page = self._request_limit(limit, self.BARS_MAX_LIMIT)

        def fetch_batch(batch: list[str]) -> dict[str, list]:
            combined: dict[str, list] = {symbol: [] for symbol in batch}
            page_token = None
            try:
                while True:
                    params = {
                        "symbols": ",".join(batch), "timeframe": timeframe,
                        "start": start.astimezone(timezone.utc).isoformat(),
                        "limit": per_page, "adjustment": "raw", "feed": self.feed, "sort": "asc",
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
                    self.warnings.append(f"Skipped bars symbol {batch[0]}: {exc}")
                    return {}
                midpoint = len(batch) // 2
                return {**fetch_batch(batch[:midpoint]), **fetch_batch(batch[midpoint:])}

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


def credential_status(client: AlpacaClient) -> str:
    """Identify which Alpaca trading environment accepts a client's configured keys.

    This module-level helper keeps the Streamlit app from depending on a
    particular AlpacaClient instance method being present when Streamlit Cloud
    reuses an older imported class object across deploys. It still performs the
    same authenticated account check and raises AlpacaError when both
    environments reject the keys.
    """
    errors = []
    environments = (("paper", client.PAPER_TRADING), ("live", client.LIVE_TRADING))
    for label, base in environments:
        try:
            payload = client._get(base, "/v2/account")
            client.diagnostics["credential_environment"] = label
            client.diagnostics["account_status"] = payload.get("status", "unknown")
            return label
        except Exception as exc:
            errors.append(f"{label}: {exc}")
    raise AlpacaError("Credentials were rejected by both Alpaca environments (" + " | ".join(errors) + ")")

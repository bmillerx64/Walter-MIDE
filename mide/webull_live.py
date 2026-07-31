"""Production Webull snapshot-and-stream cache used by Walter's live scan path.

Alpaca is currently the explicit symbol master and news/history provider.  All
live quote fields, however, are seeded from Webull OpenAPI before the Price Gate
and are subsequently refreshed only by Webull streaming events.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import hmac
import json
import logging
import os
from threading import Lock
import time
from typing import Callable, Iterable, Mapping
from urllib.parse import urlparse
import uuid

import requests

from .market_data import EventType, MarketEvent
from .market_data_providers import WebullProvider
from .webull_stream_benchmark import PahoWebullStream, Quote


LOGGER = logging.getLogger(__name__)
DEFAULT_BOOTSTRAP_URL = "https://api.webull.com/api/market-data/streaming/token"
DEFAULT_OPENAPI_URL = "https://api.webull.com"
DEFAULT_SNAPSHOT_PATH = "/market-data/quotes"
DEFAULT_TOPIC = "market-data/{symbol}"


def live_data_modes(*, alpaca_configured: bool, webull_configured: bool) -> tuple[list[str], int]:
    """Return Walter's stable provider choices and the safest available default."""
    modes = ["Live Alpaca", "Live Webull", "Demo"]
    if alpaca_configured:
        return modes, 0
    if webull_configured:
        return modes, 1
    return modes, 2


@dataclass
class CachedMarketData:
    price: float
    volume: float | None
    bid: float | None
    ask: float | None
    source_timestamp_ms: int
    received_timestamp_ms: int


def _number(value):
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def parse_webull_message(payload: bytes) -> tuple[Quote, dict]:
    """Normalize the JSON form returned by the official streaming gateway."""
    data = json.loads(payload)
    data = data.get("data", data)
    symbol = str(data.get("symbol") or data.get("ticker") or data.get("instrument_id") or "")
    price = _number(data.get("price") or data.get("last_price") or data.get("close"))
    timestamp = data.get("timestamp_ms") or data.get("timestamp") or data.get("time")
    if not symbol or price is None:
        raise ValueError("Webull message lacks a symbol or price")
    timestamp = int(timestamp or time.time_ns() // 1_000_000)
    if timestamp < 10_000_000_000:
        timestamp *= 1000
    sequence = data.get("sequence") or data.get("seq")
    return Quote(symbol.upper(), price, timestamp, int(sequence) if sequence is not None else None,
                 len(payload), _number(data.get("volume") or data.get("total_volume")),
                 _number(data.get("bid") or data.get("bid_price")),
                 _number(data.get("ask") or data.get("ask_price"))), data


class WebullBootstrap:
    """Obtain short-lived MQTT credentials with an OpenAPI-signed request."""

    def __init__(self, app_key: str, app_secret: str, *, url: str = DEFAULT_BOOTSTRAP_URL,
                 session=requests, timeout: int = 15):
        self.app_key, self._secret, self.url = app_key, app_secret, url
        self.session, self.timeout = session, timeout

    def obtain(self) -> dict:
        timestamp = str(int(time.time() * 1000))
        nonce = uuid.uuid4().hex
        path = urlparse(self.url).path
        canonical = f"POST\n{path}\n{timestamp}\n{nonce}\n"
        signature = hmac.new(self._secret.encode(), canonical.encode(), hashlib.sha256).hexdigest()
        headers = {"x-app-key": self.app_key, "x-timestamp": timestamp,
                   "x-nonce": nonce, "x-signature": signature,
                   "content-type": "application/json"}
        response = self.session.post(self.url, headers=headers, json={}, timeout=self.timeout)
        response.raise_for_status()
        body = response.json().get("data", response.json())
        aliases = {
            "host": ("host", "mqtt_host", "endpoint"),
            "username": ("username", "mqtt_username"),
            "password": ("password", "mqtt_password", "token"),
            "client_id": ("client_id", "clientId", "mqtt_client_id"),
            "topic_template": ("topic_template", "topicTemplate"),
            "port": ("port", "mqtt_port"),
        }
        normalized = {name: next((body[key] for key in keys if body.get(key) is not None), None)
                      for name, keys in aliases.items()}
        missing = [name for name in ("host", "username", "password", "client_id")
                   if not normalized[name]]
        if missing:
            raise RuntimeError("Webull bootstrap response missing: " + ", ".join(missing))
        normalized["topic_template"] = normalized["topic_template"] or DEFAULT_TOPIC
        normalized["port"] = int(normalized["port"] or 443)
        return normalized


class WebullOpenAPIClient:
    """Small signed client for the official Webull bulk snapshot operation."""

    def __init__(self, app_key: str, app_secret: str, *, base_url=DEFAULT_OPENAPI_URL,
                 snapshot_path=DEFAULT_SNAPSHOT_PATH, session=requests, timeout: int = 15):
        self.app_key, self._secret = app_key, app_secret
        self.base_url, self.snapshot_path = base_url.rstrip("/"), snapshot_path
        self.session, self.timeout = session, timeout

    def _headers(self, method: str, path: str, query: str) -> dict[str, str]:
        timestamp, nonce = str(int(time.time() * 1000)), uuid.uuid4().hex
        canonical = f"{method}\n{path}\n{timestamp}\n{nonce}\n{query}"
        signature = hmac.new(self._secret.encode(), canonical.encode(), hashlib.sha256).hexdigest()
        return {"x-app-key": self.app_key, "x-timestamp": timestamp, "x-nonce": nonce,
                "x-signature": signature, "accept": "application/json"}

    def snapshots(self, symbols: Iterable[str]) -> dict[str, dict]:
        wanted = [str(symbol).strip().upper() for symbol in symbols if str(symbol).strip()]
        if not wanted:
            return {}
        # The endpoint accepts a comma-delimited ticker list. Keep the exact
        # encoded query in the signature so credentials never enter the URL.
        params = {"symbols": ",".join(wanted)}
        prepared = requests.Request("GET", self.base_url + self.snapshot_path,
                                    params=params).prepare()
        query = urlparse(prepared.url).query
        response = self.session.get(prepared.url, headers=self._headers(
            "GET", self.snapshot_path, query), timeout=self.timeout)
        response.raise_for_status()
        body = response.json()
        rows = body.get("data", body) if isinstance(body, dict) else body
        if isinstance(rows, dict):
            rows = rows.get("quotes") or rows.get("items") or rows
        if isinstance(rows, dict):
            rows = [{**value, "symbol": key} for key, value in rows.items()]
        normalized = {}
        for row in rows or []:
            symbol = str(row.get("symbol") or row.get("ticker") or row.get("ticker_symbol") or "").upper()
            price = _number(row.get("price") or row.get("last_price") or row.get("close"))
            if not symbol or price is None:
                continue
            normalized[symbol] = {
                "latestTrade": {"p": price, "t": row.get("timestamp") or row.get("time")},
                "latestQuote": {"bp": _number(row.get("bid") or row.get("bid_price")),
                                "ap": _number(row.get("ask") or row.get("ask_price"))},
                "dailyBar": {"c": price, "v": _number(row.get("volume") or row.get("total_volume")),
                             "h": _number(row.get("high")), "l": _number(row.get("low"))},
                "prevDailyBar": {"c": _number(row.get("prev_close") or row.get("previous_close")),
                                 "v": _number(row.get("prev_volume"))},
                "market_data_provider": "Webull OpenAPI snapshot cache",
            }
        return normalized


class LiveWebullProvider(WebullProvider):
    """Webull-only quote cache, seeded by REST and refreshed by streaming."""

    provider_name = "Webull OpenAPI"

    def __init__(self, app_key: str, app_secret: str, *, fallback, bootstrap=None,
                 rest_client=None, stream_class=PahoWebullStream):
        self.fallback = fallback
        self.cache: dict[str, CachedMarketData] = {}
        self._snapshot_cache: dict[str, dict] = {}
        self._lock = Lock()
        self._subscription = None
        self._subscribed: set[str] = set()
        self._latencies = deque(maxlen=1000)
        self._stream_class = stream_class
        self._broker = None
        self.warnings = fallback.warnings
        self.diagnostics = fallback.diagnostics
        self.diagnostics["webull_stream"] = {
            "selected_provider": "WEBULL", "authentication_status": "pending",
            "stream_connection_status": "disconnected", "subscribed_symbols": 0,
            "cached_symbols": 0, "messages_received": 0, "last_message_timestamp": None,
            "stream_latency_ms": None, "subscription_failures": [],
            "disconnect_count": 0, "symbols_missing_prices": 0,
        }
        self.diagnostics["market_data_sources"] = {
            "universe_provider": "Alpaca active tradable assets",
            "snapshot_provider": "Webull OpenAPI",
            "streaming_provider": "Webull OpenAPI",
        }
        bootstrap_url = os.getenv("WEBULL_STREAM_BOOTSTRAP_URL", DEFAULT_BOOTSTRAP_URL)
        self._bootstrap = bootstrap or WebullBootstrap(app_key, app_secret, url=bootstrap_url)
        self._snapshot_client = rest_client or WebullOpenAPIClient(
            app_key, app_secret, base_url=os.getenv("WEBULL_OPENAPI_URL", DEFAULT_OPENAPI_URL))
        super().__init__(stream_factory=self._stream_factory)

    def __getattr__(self, name):
        return getattr(self.fallback, name)

    def _stream_factory(self, receive: Callable[[MarketEvent], None]):
        self._broker = self._bootstrap.obtain()
        diagnostic = self.diagnostics["webull_stream"]
        diagnostic["authentication_status"] = "authenticated"

        def parser(payload: bytes) -> Quote:
            quote, raw = parse_webull_message(payload)
            return quote

        # Paho's callback emits the normalized trade event to ``receive``.
        return self._stream_class(receive, host=self._broker["host"], port=self._broker["port"],
            username=self._broker["username"], password=self._broker["password"],
            client_id=self._broker["client_id"], topic_template=self._broker["topic_template"],
            parser=parser, on_disconnect=self._on_disconnect)

    def _on_disconnect(self) -> None:
        d = self.diagnostics["webull_stream"]
        d["disconnect_count"] += 1
        d["stream_connection_status"] = "disconnected"

    def _on_event(self, event: MarketEvent) -> None:
        now_ms = time.time_ns() // 1_000_000
        raw = event.payload
        previous = self.cache.get(event.symbol)
        value = CachedMarketData(float(raw["price"]), _number(raw.get("volume")),
            _number(raw.get("bid")), _number(raw.get("ask")), event.source_timestamp_ms, now_ms)
        if previous and value.volume is None:
            value.volume = previous.volume
        with self._lock:
            self.cache[event.symbol] = value
            latency = max(0, now_ms - event.source_timestamp_ms)
            self._latencies.append(latency)
            d = self.diagnostics["webull_stream"]
            d["cached_symbols"] = len(self.cache)
            d["symbols_missing_prices"] = len(self._subscribed - set(self.cache))
            d["messages_received"] += 1
            d["last_message_timestamp"] = datetime.fromtimestamp(now_ms / 1000, timezone.utc).isoformat()
            d["stream_latency_ms"] = round(sum(self._latencies) / len(self._latencies), 2)

    def ensure_stream(self, symbols: Iterable[str]) -> None:
        wanted = {str(symbol).strip().upper() for symbol in symbols if str(symbol).strip()}
        new = sorted(wanted - self._subscribed)
        if not new and self._subscription is not None:
            return
        d = self.diagnostics["webull_stream"]
        try:
            if self._subscription is None:
                self._subscription = self.subscribe(new, (EventType.QUOTE, EventType.TRADE), self._on_event)
                d["stream_connection_status"] = "connected"
            else:
                self._subscription.add(new)
            self._subscribed.update(new)
            d["subscribed_symbols"] = len(self._subscribed)
        except Exception as exc:
            d["authentication_status"] = "failed" if self._broker is None else d["authentication_status"]
            d["stream_connection_status"] = "error"
            d["subscription_failures"].append(f"{type(exc).__name__}: {exc}")
            self.warnings.append(f"Webull stream unavailable; cached Webull snapshot retained: {exc}")
            LOGGER.error("WEBULL stream initialization failed; cached snapshot retained: %s", exc)

    def initialize_quotes(self, symbols: Iterable[str], *, batch_size: int = 200) -> dict[str, float]:
        """Synchronously seed every available price, then immediately stream it."""
        wanted = list(dict.fromkeys(str(s).strip().upper() for s in symbols if str(s).strip()))
        for offset in range(0, len(wanted), batch_size):
            batch = wanted[offset:offset + batch_size]
            snapshots = self._snapshot_client.snapshots(batch)
            now_ms = time.time_ns() // 1_000_000
            with self._lock:
                for symbol, snapshot in snapshots.items():
                    trade, daily, quote = (snapshot.get("latestTrade") or {},
                        snapshot.get("dailyBar") or {}, snapshot.get("latestQuote") or {})
                    price = _number(trade.get("p") or daily.get("c"))
                    if price is None:
                        continue
                    self._snapshot_cache[symbol] = dict(snapshot)
                    timestamp = trade.get("t") or now_ms
                    try:
                        timestamp = int(timestamp)
                    except (TypeError, ValueError):
                        timestamp = now_ms
                    if timestamp > 10_000_000_000_000:
                        timestamp //= 1_000_000
                    self.cache[symbol] = CachedMarketData(price, _number(daily.get("v")),
                        _number(quote.get("bp")), _number(quote.get("ap")), timestamp, now_ms)
        d = self.diagnostics["webull_stream"]
        d["cached_symbols"] = len(self.cache)
        d["symbols_missing_prices"] = len(set(wanted) - set(self.cache))
        # Snapshot completion is a hard ordering boundary before subscription.
        self.ensure_stream(wanted)
        return self.latest_trades(wanted, initialize=False)

    def latest_trades(self, symbols: Iterable[str], *, initialize: bool = True) -> dict[str, float]:
        symbols = list(symbols)
        if initialize and any(symbol not in self.cache for symbol in symbols):
            return self.initialize_quotes(symbols)
        with self._lock:
            return {symbol: self.cache[symbol].price for symbol in symbols if symbol in self.cache}

    trades = latest_trades

    def snapshots(self, symbols: Iterable[str]) -> dict:
        symbols = list(symbols)
        if any(symbol not in self.cache for symbol in symbols):
            self.initialize_quotes(symbols)
        with self._lock:
            snapshots = {symbol: dict(self._snapshot_cache.get(symbol, {}))
                         for symbol in symbols if symbol in self.cache}
        with self._lock:
            cached = {symbol: self.cache.get(symbol) for symbol in symbols}
        for symbol, live in cached.items():
            if live is None:
                continue
            snapshot = snapshots.setdefault(symbol, {})
            snapshot["latestTrade"] = {**snapshot.get("latestTrade", {}), "p": live.price,
                                       "t": live.source_timestamp_ms * 1_000_000}
            if live.volume is not None:
                snapshot["dailyBar"] = {**snapshot.get("dailyBar", {}), "v": live.volume,
                                        "c": live.price}
            if live.bid is not None or live.ask is not None:
                snapshot["latestQuote"] = {**snapshot.get("latestQuote", {}),
                    "bp": live.bid, "ap": live.ask}
            snapshot["market_data_provider"] = "Webull OpenAPI streaming cache"
        return snapshots

    def news(self, *args, **kwargs):
        return self.fallback.news(*args, **kwargs)

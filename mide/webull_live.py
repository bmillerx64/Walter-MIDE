"""Production Webull streaming cache used by Walter's live scan path.

The adapter intentionally composes the existing Alpaca provider: Alpaca remains
the discovery/news and REST fallback while fresh Webull events replace its
price, quote, and volume fields.
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


class LiveWebullProvider(WebullProvider):
    """Streaming-first provider with an Alpaca provider as a safe fallback."""

    provider_name = "Webull OpenAPI"

    def __init__(self, app_key: str, app_secret: str, *, fallback, bootstrap=None,
                 stream_class=PahoWebullStream):
        self.fallback = fallback
        self.cache: dict[str, CachedMarketData] = {}
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
        }
        bootstrap_url = os.getenv("WEBULL_STREAM_BOOTSTRAP_URL", DEFAULT_BOOTSTRAP_URL)
        self._bootstrap = bootstrap or WebullBootstrap(app_key, app_secret, url=bootstrap_url)
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
            parser=parser)

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
            self.warnings.append(f"Webull stream unavailable; using Alpaca fallback: {exc}")
            LOGGER.error("WEBULL stream initialization failed; using ALPACA fallback: %s", exc)

    def latest_trades(self, symbols: Iterable[str]) -> dict[str, float]:
        symbols = list(symbols)
        self.ensure_stream(symbols)
        fallback = self.fallback.latest_trades(symbols)
        with self._lock:
            fallback.update({symbol: self.cache[symbol].price for symbol in symbols if symbol in self.cache})
        return fallback

    trades = latest_trades

    def snapshots(self, symbols: Iterable[str]) -> dict:
        symbols = list(symbols)
        self.ensure_stream(symbols)
        snapshots = self.fallback.snapshots(symbols)
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

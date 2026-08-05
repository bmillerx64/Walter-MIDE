"""Production, Webull-only market-data provider used by Walter's live scan."""

from __future__ import annotations

from collections import deque
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import logging
import re
from threading import Lock
import time
from typing import Callable, Iterable

from .market_data import EventType, MarketEvent
from .market_data_providers import WebullProvider
from .webull_stream_benchmark import Quote
from .webull_sdk import (HTTP_HOST, MAX_SNAPSHOT_SYMBOLS, SNAPSHOT_OPERATION,
                         STREAM_HOST, WebullSDKClient)
from .startup import log_startup


LOGGER = logging.getLogger(__name__)
NETWORK_TIMEOUT_SECONDS = 8
MAX_DIAGNOSTIC_SYMBOLS = 50
UNSUPPORTED_SYMBOL_PATTERNS = (
    re.compile(r"^[A-Z]{1,5}[.-]PR[A-Z]$"),
    re.compile(r"^[A-Z]{1,5}[.-]P[A-Z]$"),
)
KNOWN_UNSUPPORTED_WEBULL_SYMBOLS = {"PBR.A"}
_NETWORK_EXECUTOR = ThreadPoolExecutor(max_workers=4, thread_name_prefix="walter-network")


def _invalid_symbol_error(exc: Exception) -> bool:
    """Identify the SDK's HTTP 417 invalid-symbol response without hiding auth errors."""
    message = f"{type(exc).__name__}: {exc}".upper()
    return "INVALID_SYMBOL" in message or ("417" in message and "SYMBOL" in message)


def _extract_invalid_symbols(exc: Exception, batch: Iterable[str]) -> set[str]:
    """Return endpoint-rejected symbols named by Webull without retaining SDK objects."""
    message = f"{type(exc).__name__}: {exc}".upper()
    batch_symbols = {str(symbol).strip().upper() for symbol in batch if str(symbol).strip()}
    named = {symbol for symbol in batch_symbols if symbol in message}
    if named:
        return named
    tokens = set(re.findall(r"\b[A-Z]{1,6}(?:[./-][A-Z]{1,4})?\b", message))
    return batch_symbols & tokens


def _webull_prefilter_unsupported(symbols: Iterable[str]) -> tuple[list[str], list[str]]:
    """Exclude Webull-known unsupported preferred formats while preserving class shares."""
    accepted: list[str] = []
    excluded: list[str] = []
    for raw in symbols:
        symbol = str(raw).strip().upper()
        if not symbol:
            continue
        if symbol in KNOWN_UNSUPPORTED_WEBULL_SYMBOLS or any(
            pattern.match(symbol) for pattern in UNSUPPORTED_SYMBOL_PATTERNS
        ):
            excluded.append(symbol)
        else:
            accepted.append(symbol)
    return list(dict.fromkeys(accepted)), list(dict.fromkeys(excluded))


def live_data_modes(*, alpaca_configured: bool, webull_configured: bool) -> tuple[list[str], int]:
    """Return Walter's stable provider choices and the safest available default."""
    modes = ["Live Alpaca", "Live Webull", "Demo"]
    if webull_configured:
        return modes, 1
    if alpaca_configured:
        return modes, 0
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


class WebullOpenAPIClient:
    """Normalize official-SDK market-data responses for Walter."""

    base_url = HTTP_HOST
    snapshot_path = "/openapi/market-data/stock/snapshot"

    def __init__(self, app_key: str, app_secret: str, *, sdk_client=None,
                 extended_hours_enabled: bool = False):
        self.sdk = WebullSDKClient(app_key, app_secret, sdk_client=sdk_client)
        self.extended_hours_enabled = bool(extended_hours_enabled)

    @staticmethod
    def _rows(value: object) -> list[dict]:
        if isinstance(value, list):
            return [row for row in value if isinstance(row, dict)]
        if isinstance(value, dict):
            value = value.get("data", value)
            if isinstance(value, list):
                return [row for row in value if isinstance(row, dict)]
            if isinstance(value, dict):
                for key in ("items", "list", "rows", "snapshots", "bars"):
                    if isinstance(value.get(key), list):
                        return [row for row in value[key] if isinstance(row, dict)]
        return []

    def snapshots(self, symbols: Iterable[str]) -> dict[str, dict]:
        wanted = list(dict.fromkeys(str(s).strip().upper() for s in symbols if str(s).strip()))
        if len(wanted) > MAX_SNAPSHOT_SYMBOLS:
            raise ValueError("Webull snapshot requests are limited to 100 symbols")
        rows = self._rows(self.sdk.stock_snapshot(
            wanted, extended_hours=self.extended_hours_enabled)) if wanted else []
        normalized = {}
        for row in rows:
            symbol = str(row.get("symbol") or row.get("ticker") or row.get("ticker_symbol") or "").upper()
            price = _number(row.get("price") or row.get("last_price") or row.get("close") or row.get("latest_price"))
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
                "market_data_provider": "Webull OpenAPI SDK",
            }
        return normalized

    def bars(self, symbols: Iterable[str], *, start: datetime, timeframe="1Min",
             limit=10_000, **kwargs) -> dict[str, list[dict]]:
        output = {}
        interval = {"1Min": "m1", "30Sec": "s30"}.get(timeframe, timeframe)
        for symbol in symbols:
            payload = self.sdk.bars(symbol=symbol, category="US_STOCK", interval=interval,
                                    start_time=start.isoformat(), count=min(int(limit), 10_000),
                                    extend_hour_required=True, include_overnight=True)
            output[str(symbol).upper()] = [{
                "t": row.get("timestamp") or row.get("time") or row.get("t"),
                "o": _number(row.get("open") or row.get("o")),
                "h": _number(row.get("high") or row.get("h")),
                "l": _number(row.get("low") or row.get("l")),
                "c": _number(row.get("close") or row.get("c")),
                "v": _number(row.get("volume") or row.get("v")),
            } for row in self._rows(payload)]
        return output

    def stream(self, callback):
        return self.sdk.stream(callback)


class LiveWebullProvider(WebullProvider):
    """Webull-only quote cache, seeded by REST and refreshed by streaming."""

    provider_name = "Webull OpenAPI"

    def __init__(self, app_key: str, app_secret: str, *, fallback=None, bootstrap=None,
                 rest_client=None, stream_class=None, universe_client=None, sdk_client=None,
                 enable_streaming: bool = False, extended_hours_enabled: bool = False):
        LOGGER.info("LiveWebullProvider initialization started streaming_enabled=%s "
                    "rest_client_injected=%s sdk_client_injected=%s",
                    enable_streaming, rest_client is not None, sdk_client is not None)
        self.cache: dict[str, CachedMarketData] = {}
        self._snapshot_cache: dict[str, dict] = {}
        self._lock = Lock()
        self._subscription = None
        self._subscribed: set[str] = set()
        self._latencies = deque(maxlen=1000)
        self._unsupported_symbols: set[str] = set()
        self._stream_class = stream_class
        self._universe_client = universe_client
        self._broker = None
        self._enable_streaming = enable_streaming
        self._extended_hours_enabled = bool(extended_hours_enabled)
        if fallback is not None:
            raise ValueError("Live Webull is Webull-only; fallback providers are forbidden")
        self.warnings: list[str] = []
        self.diagnostics: dict = {}
        self.diagnostics["webull_stream"] = {
            "selected_provider": "WEBULL", "authentication_status": "pending",
            "stream_connection_status": ("disconnected" if enable_streaming else "bypassed"),
            "stream_bypass_reason": (None if enable_streaming else
                "Streaming is optional and disabled until REST snapshots are proven"),
            "subscribed_symbols": 0,
            "cached_symbols": 0, "messages_received": 0, "last_message_timestamp": None,
            "stream_latency_ms": None, "subscription_failures": [],
            "disconnect_count": 0, "symbols_missing_prices": 0,
            "discovered_symbols": 0, "cached_snapshot_symbols": 0,
            "cached_snapshot_loaded": False, "snapshot_rest_succeeded": None,
            "snapshot_initial_symbol_count": 0, "snapshot_prefilter_excluded_count": 0,
            "snapshot_rejected_by_webull_count": 0, "snapshot_retry_count": 0,
            "snapshot_successful_count": 0, "snapshot_supported_universe_count": 0,
            "snapshot_unsupported_symbols_total": 0,
        }
        self.diagnostics["market_data_sources"] = {
            "universe_provider": "Alpaca Trading API",
            "quote_provider": "Webull OpenAPI SDK",
            "bars_provider": "Webull OpenAPI SDK",
            "streaming_provider": "Webull OpenAPI SDK",
        }
        self._bootstrap = bootstrap
        self._snapshot_client = rest_client or WebullOpenAPIClient(
            app_key, app_secret, sdk_client=sdk_client,
            extended_hours_enabled=self._extended_hours_enabled)
        super().__init__(stream_factory=self._stream_factory)
        LOGGER.info("LiveWebullProvider initialization complete streaming_status=%s",
                    self.diagnostics["webull_stream"]["stream_connection_status"])

    def pipeline_sources(self) -> list[dict[str, str]]:
        """Describe every provider invoked by Live Webull mode."""
        return [
            {
                "Stage": "Universe (tradable symbol list)",
                "Actual provider": "Alpaca Trading API",
                "Endpoint / operation": "GET /v2/assets (symbol master only)",
                "Code path": "build_seed_symbols → LiveWebullProvider.assets → AlpacaProvider.assets",
                "Alpaca used": "Yes — symbol master only",
            },
            {
                "Stage": "Quote / snapshot retrieval",
                "Actual provider": "Webull OpenAPI SDK",
                "Endpoint / operation": SNAPSHOT_OPERATION + (
                    " (≤100 symbols; US_STOCK; extended/overnight explicitly enabled)"
                    if self._extended_hours_enabled else
                    " (≤100 symbols; US_STOCK; regular session)"),
                "Code path": "app._run_live_pipeline.<locals>.discover → LiveWebullProvider.initialize_quotes → WebullOpenAPIClient.snapshots; then LiveWebullProvider.snapshots reads the Webull cache",
                "Alpaca used": "No",
            },
            {
                "Stage": "Streaming quotes",
                "Actual provider": "Webull OpenAPI SDK",
                "Endpoint / operation": f"SDK MQTT subscribe via {STREAM_HOST}",
                "Code path": "LiveWebullProvider.ensure_stream → official SDK market-data stream",
                "Alpaca used": "No",
            },
            {
                "Stage": "News",
                "Actual provider": "None (provider abstraction)",
                "Endpoint / operation": "Webull OpenAPI has News Summary but no raw article feed; no external call",
                "Code path": "NewsService → UnavailableNewsProvider",
                "Alpaca used": "No",
            },
            {
                "Stage": "VWAP / volume calculations",
                "Actual provider": "Webull OpenAPI SDK + Walter local calculations",
                "Endpoint / operation": "SDK stock bars; session_vwap and volume metrics run locally",
                "Code path": "analyze_candidates → LiveWebullProvider.bars → WebullOpenAPIClient.bars",
                "Alpaca used": "No",
            },
            {
                "Stage": "Scanning / filtering",
                "Actual provider": "Walter local pipeline (using the inputs above)",
                "Endpoint / operation": "No provider endpoint; in-process gates, scoring, ranking, and filtering",
                "Code path": "WalterArchitectureV1.run → discovery.prefilter_snapshots / analyze_candidates → scanner_v2 and scoring → trader_priority_sort_key",
                "Alpaca used": "No",
            },
        ]

    def assets(self):
        if self._universe_client is None:
            raise RuntimeError("Alpaca Trading API symbol-master client is not configured")
        return self._universe_client.assets()

    def bars(self, symbols, **kwargs):
        return self._snapshot_client.bars(symbols, **kwargs)

    @staticmethod
    def bars_frame(rows):
        import pandas as pd
        frame = pd.DataFrame(rows)
        if frame.empty:
            return frame
        frame = frame.rename(columns={"t": "timestamp", "o": "open", "h": "high",
                                      "l": "low", "c": "close", "v": "volume"})
        frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True)
        return frame.set_index("timestamp").sort_index()

    def news(self, *args, **kwargs):
        return []

    def _stream_factory(self, receive: Callable[[MarketEvent], None]):
        diagnostic = self.diagnostics["webull_stream"]
        diagnostic["authentication_status"] = "authenticated"
        if self._stream_class is not None and self._bootstrap is not None:
            # Test-only injection boundary; production streaming is SDK-owned.
            broker = self._bootstrap.obtain()
            return self._stream_class(receive, **broker)
        return self._snapshot_client.stream(receive)

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

    def ensure_stream(self, symbols: Iterable[str]) -> bool:
        """Attempt streaming without making it a prerequisite for cached data."""
        wanted = {str(symbol).strip().upper() for symbol in symbols if str(symbol).strip()}
        new = sorted(wanted - self._subscribed)
        if not new and self._subscription is not None:
            return True
        d = self.diagnostics["webull_stream"]
        try:
            if self._subscription is None:
                log_startup("opening MQTT/WebSocket")
                self._subscription = self.subscribe(new, (EventType.QUOTE, EventType.TRADE), self._on_event)
                d["stream_connection_status"] = "connected"
            else:
                self._subscription.add(new)
            self._subscribed.update(new)
            d["subscribed_symbols"] = len(self._subscribed)
            return True
        except Exception as exc:
            d["authentication_status"] = "failed" if self._broker is None else d["authentication_status"]
            d["stream_connection_status"] = "error"
            d["subscription_failures"].append(f"{type(exc).__name__}: {exc}")
            self.warnings.append(f"Webull stream unavailable; cached Webull snapshot retained: {exc}")
            LOGGER.error(
                "WEBULL stream initialization failed; entering snapshot-only mode "
                "cached_snapshot_symbols=%s error=%s", len(self._snapshot_cache), exc,
            )
            return False

    def initialize_quotes(self, symbols: Iterable[str], *, batch_size: int = MAX_SNAPSHOT_SYMBOLS) -> dict[str, float]:
        """Synchronously seed prices; optional SDK streaming starts only after proof."""
        initial = list(dict.fromkeys(str(s).strip().upper() for s in symbols if str(s).strip()))
        prefiltered, prefilter_excluded = _webull_prefilter_unsupported(initial)
        self._unsupported_symbols.update(prefilter_excluded)
        wanted = [symbol for symbol in prefiltered if symbol not in self._unsupported_symbols]
        batch_size = max(1, min(int(batch_size), MAX_SNAPSHOT_SYMBOLS))
        d = self.diagnostics["webull_stream"]
        d["discovered_symbols"] = len(wanted)
        d["snapshot_initial_symbol_count"] = len(initial)
        d["snapshot_prefilter_excluded_count"] = len(prefilter_excluded)
        d["snapshot_rejected_by_webull_count"] = 0
        d["snapshot_retry_count"] = 0
        d["snapshot_successful_count"] = 0
        d["snapshot_supported_universe_count"] = 0
        d["snapshot_unsupported_symbols"] = sorted(self._unsupported_symbols)[:MAX_DIAGNOSTIC_SYMBOLS]
        d["snapshot_unsupported_symbols_total"] = len(self._unsupported_symbols)
        LOGGER.info(
            "WEBULL universe before snapshot initial_symbols=%s prefilter_excluded=%s requestable_symbols=%s",
            len(initial), len(prefilter_excluded), len(wanted),
        )
        rest_succeeded = True

        def record_invalid_symbols(invalid: Iterable[str]) -> set[str]:
            """Blacklist endpoint-rejected tickers once while keeping bounded diagnostics."""
            new_invalid = {
                str(symbol).strip().upper() for symbol in invalid
                if str(symbol).strip() and str(symbol).strip().upper() not in self._unsupported_symbols
            }
            if not new_invalid:
                return set()
            self._unsupported_symbols.update(new_invalid)
            d["snapshot_rejected_by_webull_count"] += len(new_invalid)
            d["snapshot_unsupported_symbols"] = sorted(self._unsupported_symbols)[:MAX_DIAGNOSTIC_SYMBOLS]
            d["snapshot_unsupported_symbols_total"] = len(self._unsupported_symbols)
            self.warnings.append(
                "Skipped unsupported Webull snapshot symbols: " + ", ".join(sorted(new_invalid)[:10])
            )
            LOGGER.warning("WEBULL skipped invalid snapshot symbols count=%s symbols=%s",
                           len(new_invalid), sorted(new_invalid)[:10])
            return new_invalid

        def request_once(batch: list[str]) -> dict[str, dict]:
            future = _NETWORK_EXECUTOR.submit(self._snapshot_client.snapshots, batch)
            try:
                return future.result(timeout=NETWORK_TIMEOUT_SECONDS)
            except FutureTimeoutError:
                future.cancel()
                raise

        def fetch(batch: list[str]) -> dict[str, dict]:
            """Retry INVALID_SYMBOL failures only after removing identified invalid symbols."""
            batch = [symbol for symbol in batch if symbol not in self._unsupported_symbols]
            if not batch:
                return {}
            try:
                return request_once(batch)
            except Exception as exc:
                if not _invalid_symbol_error(exc):
                    raise
                invalid = record_invalid_symbols(_extract_invalid_symbols(exc, batch))
                if invalid:
                    remaining = [symbol for symbol in batch if symbol not in invalid]
                    if remaining:
                        d["snapshot_retry_count"] += 1
                        return fetch(remaining)
                    return {}
                if len(batch) == 1:
                    record_invalid_symbols(batch)
                    return {}
                midpoint = len(batch) // 2
                d["snapshot_retry_count"] += 2
                return {**fetch(batch[:midpoint]), **fetch(batch[midpoint:])}

        for offset in range(0, len(wanted), batch_size):
            batch = wanted[offset:offset + batch_size]
            try:
                snapshots = fetch(batch)
            except FutureTimeoutError:
                LOGGER.error("Webull snapshot timed out after %ss", NETWORK_TIMEOUT_SECONDS)
                snapshots = {}
                rest_succeeded = False
            except Exception as exc:
                rest_succeeded = False
                d["snapshot_rest_succeeded"] = False
                LOGGER.error(
                    "WEBULL snapshot REST failed independently of streaming batch_offset=%s batch_symbols=%s error_type=%s",
                    offset, len(batch), type(exc).__name__,
                )
                raise
            else:
                LOGGER.info(
                    "WEBULL snapshot REST succeeded independently of streaming batch_offset=%s requested_symbols=%s returned_symbols=%s",
                    offset, len(batch), len(snapshots),
                )
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
        d["snapshot_rest_succeeded"] = rest_succeeded
        d["cached_symbols"] = len(self.cache)
        d["cached_snapshot_symbols"] = len(self._snapshot_cache)
        d["snapshot_successful_count"] = len(self._snapshot_cache)
        d["snapshot_supported_universe_count"] = len([s for s in wanted if s not in self._unsupported_symbols])
        d["symbols_missing_prices"] = len(set(wanted) - set(self.cache) - self._unsupported_symbols)
        LOGGER.info(
            "WEBULL snapshot seed complete initial_symbols=%s prefilter_excluded=%s webull_rejected=%s retries=%s successful_snapshots=%s supported_universe=%s",
            len(initial), d["snapshot_prefilter_excluded_count"], d["snapshot_rejected_by_webull_count"],
            d["snapshot_retry_count"], d["snapshot_successful_count"], d["snapshot_supported_universe_count"],
        )
        if not self._enable_streaming:
            LOGGER.info("WEBULL streaming bypassed after snapshot proof; cached_symbols=%s",
                        len(self.cache))
            return self.latest_trades(wanted, initialize=False)
        stream_future = _NETWORK_EXECUTOR.submit(self.ensure_stream, wanted)
        try:
            stream_future.result(timeout=NETWORK_TIMEOUT_SECONDS)
        except FutureTimeoutError:
            stream_future.cancel()
            message = f"Webull stream initialization timed out after {NETWORK_TIMEOUT_SECONDS}s"
            self.diagnostics["webull_stream"]["stream_connection_status"] = "error"
            self.diagnostics["webull_stream"]["subscription_failures"].append(message)
            self.warnings.append(message)
            LOGGER.error(message)
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
            cached_snapshot_count = sum(
                1 for symbol in symbols if symbol in self._snapshot_cache
            )
        d = self.diagnostics["webull_stream"]
        d["cached_snapshot_loaded"] = cached_snapshot_count > 0
        d["cached_snapshot_symbols"] = len(self._snapshot_cache)
        LOGGER.info(
            "WEBULL cached snapshot load requested_symbols=%s loaded=%s "
            "loaded_symbols=%s cached_snapshot_symbols=%s",
            len(symbols), d["cached_snapshot_loaded"], cached_snapshot_count,
            len(self._snapshot_cache),
        )
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

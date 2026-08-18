"""Production, Webull-only market-data provider used by Walter's live scan."""

from __future__ import annotations

from collections import deque
from concurrent.futures import (ThreadPoolExecutor, TimeoutError as FutureTimeoutError,
                                as_completed)
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
                         STREAM_HOST, WebullSDKClient, _invalid_history_symbol)
from .startup import log_startup
from . import webull_debug_log as _debug_log


LOGGER = logging.getLogger(__name__)
NETWORK_TIMEOUT_SECONDS = 8
WEBULL_HISTORY_BATCH_MAX = 20
WEBULL_HISTORY_MAX_CONCURRENCY = 4
_NETWORK_EXECUTOR = ThreadPoolExecutor(max_workers=4, thread_name_prefix="walter-network")
_WEBULL_UNSUPPORTED_SYMBOL = re.compile(r"(?:\.|-)WI$", re.IGNORECASE)


def webull_snapshot_symbol_supported(symbol: object) -> bool:
    """Reject security suffixes known not to be accepted by stock snapshots.

    Security-type metadata is filtered while constructing the universe.  This
    last-mile check covers when-issued tickers even when only a symbol reaches
    the provider.
    """
    value = str(symbol or "").strip().upper()
    return bool(value) and not _WEBULL_UNSUPPORTED_SYMBOL.search(value)


def _invalid_symbol_error(exc: Exception) -> bool:
    """Identify the SDK's HTTP 417 invalid-symbol response without hiding auth errors."""
    message = f"{type(exc).__name__}: {exc}".upper()
    return "INVALID_SYMBOL" in message or ("417" in message and "SYMBOL" in message)


_INVALID_SNAPSHOT_SYMBOLS = re.compile(
    r"symbols?\s+does\s+not\s+exist\s+in\s+the\s+category\s*\.\s*\[([^\[\]]+)\]",
    re.IGNORECASE,
)


def _invalid_snapshot_symbols(exc: Exception) -> tuple[str, ...]:
    """Extract Webull's explicit invalid-symbol list from a snapshot 417."""
    if not _invalid_symbol_error(exc):
        return ()
    match = _INVALID_SNAPSHOT_SYMBOLS.search(str(exc))
    if not match:
        return ()
    symbols = tuple(part.strip().upper() for part in match.group(1).split(","))
    if not symbols or any(not re.fullmatch(r"[A-Z0-9][A-Z0-9.\-]*", symbol)
                          for symbol in symbols):
        return ()
    return tuple(dict.fromkeys(symbols))


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
        self.history_call_diagnostics = {"batch_calls": 0, "single_fallback_calls": 0}

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
        raw_response = None
        try:
            raw_response = self.sdk.stock_snapshot(
                wanted, extended_hours=self.extended_hours_enabled) if wanted else []
            rows = self._rows(raw_response)
        except Exception as exc:
            _debug_log.log_snapshot_attempt(
                symbols=wanted,
                raw_response=raw_response,
                normalized=None,
                error=exc,
            )
            raise
        self.last_snapshot_rows_decoded = len(rows)
        normalized = {}
        for row in rows:
            symbol = str(row.get("symbol") or row.get("ticker") or row.get("ticker_symbol") or "").upper()
            price = _number(row.get("price") or row.get("last_price") or row.get("close") or row.get("latest_price"))
            if not symbol or price is None:
                continue
            normalized[symbol] = {
                "latestTrade": {"p": price, "t": row.get("last_trade_time") or
                                row.get("timestamp") or row.get("time")},
                "latestQuote": {"bp": _number(row.get("bid") or row.get("bid_price")),
                                "ap": _number(row.get("ask") or row.get("ask_price"))},
                "dailyBar": {"c": price, "v": _number(row.get("volume") or row.get("total_volume")),
                             "h": _number(row.get("high")), "l": _number(row.get("low"))},
                "prevDailyBar": {"c": _number(row.get("pre_close") or row.get("prev_close") or
                                                row.get("previous_close")),
                                 "v": _number(row.get("prev_volume"))},
                "market_data_provider": "Webull OpenAPI SDK",
            }
        self.last_snapshot_rows_normalized = len(normalized)
        _debug_log.log_snapshot_attempt(
            symbols=wanted,
            raw_response=raw_response,
            normalized=normalized,
            error=None,
        )
        return normalized

    def bars(self, symbols: Iterable[str], *, start: datetime, timeframe="1Min",
             limit=10_000, **kwargs) -> dict[str, list[dict]]:
        wanted = list(dict.fromkeys(
            str(symbol).strip().upper() for symbol in symbols if str(symbol).strip()
        ))
        output: dict[str, list[dict]] = {}
        if str(timeframe).strip().lower() in {"30sec", "30s", "s30"}:
            raise ValueError(
                "Webull OpenAPI historical bars do not support 30-second timespan"
            )
        interval = {"1Min": "m1"}.get(timeframe, timeframe)
        end = kwargs.get("end")
        force_batch = bool(kwargs.get("force_batch"))
        call_reason = str(kwargs.get("history_reason") or "direct_single_symbol")

        def normalize(rows):
            return [{
                "t": row.get("timestamp") or row.get("time") or row.get("t"),
                "o": _number(row.get("open") or row.get("o")),
                "h": _number(row.get("high") or row.get("h")),
                "l": _number(row.get("low") or row.get("l")),
                "c": _number(row.get("close") or row.get("c")),
                "v": _number(row.get("volume") or row.get("v")),
            } for row in rows]

        def single(symbol, reason):
            LOGGER.warning(
                "WEBULL single-symbol history symbol=%s reason=%s", symbol, reason
            )
            payload = self.sdk.bars(symbol=symbol, category="US_STOCK", interval=interval,
                                    start_time=start.isoformat(), count=min(int(limit), 10_000),
                                    end_time=end.isoformat() if end else None,
                                    extend_hour_required=True, include_overnight=True)
            rows = normalize(self._rows(payload))
            with result_lock:
                output[symbol] = rows

        def grouped(payload):
            """Decode SDK batch envelopes without accepting ambiguous bar rows."""
            value = payload.get("data", payload.get("result", payload)) \
                if isinstance(payload, dict) else payload
            groups = {}
            if isinstance(value, dict):
                for symbol, rows in value.items():
                    key = str(symbol).upper()
                    decoded = self._rows(rows)
                    if key in wanted and (decoded or rows == []):
                        groups[key] = decoded
            elif isinstance(value, list):
                for item in value:
                    if not isinstance(item, dict):
                        continue
                    symbol = str(item.get("symbol") or item.get("ticker") or
                                 item.get("ticker_symbol") or "").upper()
                    if symbol not in wanted:
                        continue
                    rows = self._rows(item.get("bars", item.get("data", item.get("result", []))))
                    groups.setdefault(symbol, []).extend(rows)
            return groups

        fallback_count = 0
        result_lock = Lock()

        def fallback(batch, reason):
            nonlocal fallback_count
            with result_lock:
                fallback_count += len(batch)
                self.history_call_diagnostics["single_fallback_calls"] += len(batch)
            LOGGER.warning("WEBULL batch history fallback batch_size=%d reason=%s",
                           len(batch), reason)
            for symbol in batch:
                single(symbol, reason)

        def request_batch(batch):
            batch_started = time.monotonic()
            returned_count = 0
            batch_fallback_count = 0
            try:
                with result_lock:
                    self.history_call_diagnostics["batch_calls"] += 1
                payload = self.sdk.batch_bars(
                    symbols=batch, category="US_STOCK", interval=interval,
                    start_time=start.isoformat(), count=min(int(limit), 10_000),
                    end_time=end.isoformat() if end else None,
                    extend_hour_required=True, include_overnight=True,
                )
                decoded = grouped(payload)
                if not decoded:
                    fallback(batch, "fallback_undecodable_batch")
                    batch_fallback_count = len(batch)
                    return
                for symbol, rows in decoded.items():
                    with result_lock:
                        output[symbol] = normalize(rows)
                missing = [symbol for symbol in batch if symbol not in decoded]
                if missing:
                    fallback(missing, "fallback_missing_batch_symbol")
                returned_count = len(decoded)
                batch_fallback_count = len(missing)
            except Exception as exc:
                # A 417 may identify only that the request contains a bad symbol.
                # Bisect it so valid peers continue to benefit from batch history.
                if _invalid_history_symbol(exc) and len(batch) > 1:
                    midpoint = len(batch) // 2
                    LOGGER.warning("WEBULL batch history failed batch_size=%d "
                                   "reason=fallback_invalid_symbol; isolating invalid symbol",
                                   len(batch))
                    request_batch(batch[:midpoint])
                    request_batch(batch[midpoint:])
                else:
                    reason = ("fallback_invalid_symbol" if _invalid_history_symbol(exc)
                              else "fallback_batch_error")
                    fallback(batch, reason)
                    batch_fallback_count = len(batch)
            finally:
                LOGGER.warning(
                    "WEBULL batch history batch_size=%d elapsed_seconds=%.3f "
                    "returned_symbols=%d returned_bars=%d fallback_count=%d",
                    len(batch), time.monotonic() - batch_started, returned_count,
                    sum(len(output.get(symbol, ())) for symbol in batch),
                    batch_fallback_count,
                )

        if len(wanted) == 1 and not force_batch:
            started = time.monotonic()
            single(wanted[0], call_reason)
            LOGGER.warning(
                "WEBULL history complete total_symbols=1 count_per_symbol=%d batches=1 "
                "concurrency=1 elapsed_seconds=%.3f returned_symbols=%d returned_bars=%d "
                "fallback_count=0",
                min(int(limit), 1200), time.monotonic() - started, len(output),
                sum(len(rows) for rows in output.values()),
            )
        elif wanted:
            started = time.monotonic()
            batches = [wanted[offset:offset + WEBULL_HISTORY_BATCH_MAX]
                       for offset in range(0, len(wanted), WEBULL_HISTORY_BATCH_MAX)]
            concurrency = min(WEBULL_HISTORY_MAX_CONCURRENCY, len(batches))
            # SDK 2.0.16 builds a request, signature, and Response locally for each
            # call; the shared ApiClient contributes read-only credentials/config.
            with ThreadPoolExecutor(max_workers=concurrency,
                                    thread_name_prefix="webull-history") as executor:
                futures = [executor.submit(request_batch, batch) for batch in batches]
                for future in as_completed(futures):
                    future.result()
            LOGGER.warning(
                "WEBULL batch history complete total_symbols=%d count_per_symbol=%d "
                "batches=%d concurrency=%d elapsed_seconds=%.3f returned_symbols=%d "
                "returned_bars=%d fallback_count=%d",
                len(wanted), min(int(limit), 1200), len(batches), concurrency,
                time.monotonic() - started, len(output),
                sum(len(rows) for rows in output.values()), fallback_count,
            )
        return {symbol: output[symbol] for symbol in wanted if symbol in output}

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
        }
        self.diagnostics["market_data_sources"] = {
            "universe_provider": "Alpaca Trading API",
            "quote_provider": "Webull OpenAPI SDK",
            "bars_provider": "Webull OpenAPI SDK",
            "streaming_provider": "Webull OpenAPI SDK",
        }
        # Populated by the native-radar assets() call so initialize_quotes can
        # fall back to radar prices when the REST snapshot returns no data.
        self._native_radar_prices: dict[str, dict] = {}
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
        """Normalize Webull rows without falling back to dateutil per timestamp."""
        import pandas as pd
        frame = pd.DataFrame(rows)
        if frame.empty:
            return frame
        frame = frame.rename(columns={"t": "timestamp", "o": "open", "h": "high",
                                      "l": "low", "c": "close", "v": "volume"})
        timestamps = frame["timestamp"]
        numeric = pd.to_numeric(timestamps, errors="coerce")
        non_null = timestamps.notna()
        if non_null.any() and numeric[non_null].notna().all():
            magnitude = float(numeric[non_null].abs().median())
            if magnitude >= 1e17:
                unit = "ns"
            elif magnitude >= 1e14:
                unit = "us"
            elif magnitude >= 1e11:
                unit = "ms"
            else:
                unit = "s"
            frame["timestamp"] = pd.to_datetime(
                numeric, unit=unit, utc=True, errors="coerce"
            )
        else:
            frame["timestamp"] = pd.to_datetime(
                timestamps, utc=True, format="mixed", errors="coerce"
            )
        frame = frame.dropna(subset=["timestamp"])
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
        submitted = list(dict.fromkeys(str(s).strip().upper() for s in symbols if str(s).strip()))
        wanted = [symbol for symbol in submitted if webull_snapshot_symbol_supported(symbol)]
        rejected = [symbol for symbol in submitted if symbol not in wanted]
        batch_size = max(1, min(int(batch_size), MAX_SNAPSHOT_SYMBOLS))
        d = self.diagnostics["webull_stream"]
        d["discovered_symbols"] = len(submitted)
        d["snapshot_unsupported_symbols"] = rejected
        for symbol in rejected:
            self.warnings.append(f"Skipped unsupported Webull snapshot symbol {symbol}")
        LOGGER.info("WEBULL universe before snapshot discovered_symbols=%s supported_symbols=%s "
                    "rejected_symbols=%s", len(submitted), len(wanted), len(rejected))
        rest_succeeded = True
        snapshot_rows_decoded = 0
        snapshot_rows_normalized = 0

        def fetch(batch):
            """Bisect only INVALID_SYMBOL failures so one ticker cannot poison a batch."""
            future = _NETWORK_EXECUTOR.submit(self._snapshot_client.snapshots, batch)
            try:
                return future.result(timeout=NETWORK_TIMEOUT_SECONDS)
            except FutureTimeoutError:
                future.cancel()
                raise
            except Exception as exc:
                if not _invalid_symbol_error(exc):
                    raise
                identified = set(_invalid_snapshot_symbols(exc))
                invalid = [symbol for symbol in batch if symbol in identified]
                if invalid:
                    for symbol in invalid:
                        if symbol not in d["snapshot_unsupported_symbols"]:
                            d["snapshot_unsupported_symbols"].append(symbol)
                        self.warnings.append(
                            f"Skipped unsupported Webull snapshot symbol {symbol}: "
                            "Webull returned HTTP 417 INVALID_SYMBOL"
                        )
                    remaining = [symbol for symbol in batch if symbol not in identified]
                    LOGGER.warning(
                        "WEBULL snapshot rejected invalid symbols symbols=%s "
                        "batch_size=%d retry_count=%d",
                        invalid, len(batch), int(bool(remaining)),
                    )
                    return fetch(remaining) if remaining else {}
                if len(batch) == 1:
                    symbol = batch[0]
                    d["snapshot_unsupported_symbols"].append(symbol)
                    self.warnings.append(
                        f"Skipped unsupported Webull snapshot symbol {symbol}: "
                        "Webull returned HTTP 417 INVALID_SYMBOL"
                    )
                    LOGGER.warning("WEBULL skipped invalid snapshot symbol symbol=%s", symbol)
                    return {}
                midpoint = len(batch) // 2
                return {**fetch(batch[:midpoint]), **fetch(batch[midpoint:])}

        for offset in range(0, len(wanted), batch_size):
            batch = wanted[offset:offset + batch_size]
            for counter in ("last_snapshot_rows_decoded", "last_snapshot_rows_normalized"):
                if hasattr(self._snapshot_client, counter):
                    setattr(self._snapshot_client, counter, 0)
            # Every Webull socket is opened by a network worker. The Streamlit
            # script has already rendered its shell before a scan can reach here.
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
                    "WEBULL snapshot REST failed independently of streaming "
                    "batch_offset=%s batch_symbols=%s error=%s",
                    offset, len(batch), exc,
                )
                raise
            else:
                LOGGER.info(
                    "WEBULL snapshot REST succeeded independently of streaming "
                    "batch_offset=%s requested_symbols=%s returned_symbols=%s",
                    offset, len(batch), len(snapshots),
                )
            snapshot_rows_decoded += int(getattr(
                self._snapshot_client, "last_snapshot_rows_decoded", len(snapshots)))
            snapshot_rows_normalized += int(getattr(
                self._snapshot_client, "last_snapshot_rows_normalized", len(snapshots)))
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
        d["symbols_missing_prices"] = len(set(wanted) - set(self.cache))
        LOGGER.info(
            "WEBULL snapshot initialization summary discovered_symbols=%s "
            "snapshot_rows_decoded=%s snapshot_rows_normalized=%s "
            "cached_snapshot_symbols=%s symbols_missing_prices=%s",
            len(submitted), snapshot_rows_decoded, snapshot_rows_normalized,
            len(self._snapshot_cache), d["symbols_missing_prices"],
        )
        # Fall back to native radar prices for symbols where the REST snapshot
        # returned no valid price data.  The radar already carries price,
        # change_ratio (in percent), and volume from the discovery feeds, so we
        # can reconstruct a minimal snapshot that lets prefilter_snapshots run.
        native_prices = self._native_radar_prices
        if native_prices:
            fallback_count = 0
            now_ms = time.time_ns() // 1_000_000
            with self._lock:
                for symbol in wanted:
                    if symbol in self.cache:
                        continue
                    radar = native_prices.get(symbol)
                    if radar is None:
                        continue
                    price = _number(radar.get("price"))
                    if price is None:
                        continue
                    volume = _number(radar.get("volume"))
                    change_ratio = _number(radar.get("change_ratio"))
                    # change_ratio is in percent (e.g. 50.33 for +50.33 %)
                    prev_close = (
                        price / (1 + change_ratio / 100)
                        if change_ratio is not None and change_ratio != -100
                        else None
                    )
                    snapshot = {
                        "latestTrade": {"p": price},
                        "latestQuote": {},
                        "dailyBar": {"c": price, "v": volume, "h": price, "l": price},
                        "prevDailyBar": {"c": prev_close, "v": None},
                        "market_data_provider": "Webull native radar fallback",
                    }
                    self._snapshot_cache[symbol] = snapshot
                    self.cache[symbol] = CachedMarketData(
                        price, volume, None, None, now_ms, now_ms
                    )
                    fallback_count += 1
            if fallback_count:
                d["native_radar_fallback_symbols"] = fallback_count
                d["symbols_missing_prices"] = len(set(wanted) - set(self.cache))
                LOGGER.info(
                    "WEBULL native radar fallback applied fallback_symbols=%s "
                    "remaining_missing=%s",
                    fallback_count, d["symbols_missing_prices"],
                )
        # Snapshot completion is a hard ordering boundary before any optional
        # subscription. The obsolete hand-written token bootstrap is deliberately
        # absent: only the official SDK may initialize a stream.
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

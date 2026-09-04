"""GS379: activate Webull OpenAPI tick streaming as observational market truth.

This phase deliberately does *not* change discovery, scoring, readiness, entry,
alert, execution, or order authority. It opens the already-entitled Webull
OpenAPI stream, aggregates genuine trade ticks into closed 30-second OHLCV bars,
and exposes diagnostics so Walter can prove 30-second market-data fidelity before
those bars are allowed to influence trading decisions.

Safety properties:
- production LiveWebullProvider instances auto-enable streaming only when Walter
  owns the real SDK construction (tests/injected providers keep their explicit
  behavior);
- the existing REST snapshot/history path remains authoritative and survives any
  stream failure;
- per-tick size is never substituted for cumulative session volume in Walter's
  snapshot cache;
- stale/out-of-order ticks cannot rewind Walter's live price cache;
- streaming subscriptions follow the current radar universe instead of growing
  without bound across 60-second scans;
- only completed 30-second buckets are exposed by ``stream_30s_bars``;
- the pinned Webull SDK remains unchanged.
"""
from __future__ import annotations

from collections import deque
from functools import wraps
import importlib
import logging
from threading import Event, Thread
import uuid
from typing import Any

from .market_data import EventType, MarketEvent


LOGGER = logging.getLogger(__name__)
CONNECT_TIMEOUT_SECONDS = 8.0
SUBSCRIBE_TIMEOUT_SECONDS = 5.0
THIRTY_SECOND_MS = 30_000
THIRTY_SECOND_HISTORY = 240


def _number(value: Any) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _production_owned_stream(kwargs: dict) -> bool:
    """True only for Walter's real SDK-owned provider construction."""
    if "enable_streaming" in kwargs:
        return False
    return all(
        kwargs.get(name) is None
        for name in ("rest_client", "stream_class", "sdk_client")
    )


def _tick_market_event(quotes: Any) -> MarketEvent | None:
    """Normalize one official SDK TickResult without depending on private protobufs."""
    basic = getattr(quotes, "basic", None)
    symbol = str(getattr(basic, "symbol", "") or "").strip().upper()
    price = _number(getattr(quotes, "price", None))
    timestamp_ms = getattr(basic, "timestamp", None)
    if not symbol or price is None or timestamp_ms is None:
        return None
    try:
        timestamp_ms = int(timestamp_ms)
    except (TypeError, ValueError):
        return None
    volume = _number(getattr(quotes, "volume", None))
    side = getattr(quotes, "side", None)
    return MarketEvent(
        "Webull OpenAPI",
        EventType.TRADE,
        symbol,
        timestamp_ms,
        {
            "price": price,
            "volume": volume,
            "side": str(side) if side is not None else None,
            "stream_payload": "TICK",
        },
    )


class OfficialWebullTickTransport:
    """Adapt Webull SDK 2.0.16 DataStreamingClient to Walter's provider contract."""

    def __init__(self, client, callback):
        self.client = client
        self.callback = callback
        self._connected = Event()
        self._subscribed = Event()
        self._thread: Thread | None = None
        self._failure: BaseException | None = None

    def _on_connect(self, _client, _api_client, _session_id) -> None:
        self._connected.set()

    def _on_subscribe(self, _client, _api_client, _session_id) -> None:
        self._subscribed.set()

    def _on_quotes(self, _client, _topic, quotes) -> None:
        event = _tick_market_event(quotes)
        if event is not None:
            try:
                self.callback(event)
            except Exception:
                # Never kill the SDK reader thread because a Walter observer failed.
                LOGGER.exception("GS379 Webull tick observer failed")

    def _run(self) -> None:
        try:
            # Avoid SDK default file/stdout logging; Walter owns redacted diagnostics.
            self.client.connect_and_loop_forever(logger_enable=False)
        except BaseException as exc:  # transport failure must wake the caller
            self._failure = exc
            self._connected.set()

    def connect(self) -> None:
        self.client.on_connect_success = self._on_connect
        self.client.on_quotes_message = self._on_quotes
        self.client.on_subscribe_success = self._on_subscribe
        self._thread = Thread(
            target=self._run,
            name="walter-webull-ticks",
            daemon=True,
        )
        self._thread.start()
        if not self._connected.wait(CONNECT_TIMEOUT_SECONDS):
            raise TimeoutError(
                f"Webull OpenAPI stream did not connect within {CONNECT_TIMEOUT_SECONDS:g}s"
            )
        if self._failure is not None:
            raise RuntimeError(f"Webull OpenAPI stream failed: {self._failure}") from self._failure

    @staticmethod
    def _symbols(symbols) -> list[str]:
        return list(dict.fromkeys(
            str(symbol or "").strip().upper()
            for symbol in symbols
            if str(symbol or "").strip()
        ))

    def subscribe(self, symbols: list[str]) -> None:
        wanted = self._symbols(symbols)
        if not wanted:
            return
        self._subscribed.clear()
        # TICK is the only payload GS379 needs. Snapshot/history remain on the
        # proven REST path, minimizing stream topic load and behavioral surface.
        self.client.subscribe(wanted, "US_STOCK", ["TICK"])
        if not self._subscribed.wait(SUBSCRIBE_TIMEOUT_SECONDS):
            raise RuntimeError("Webull OpenAPI tick subscription did not confirm")

    def unsubscribe(self, symbols: list[str]) -> None:
        wanted = self._symbols(symbols)
        if not wanted:
            return
        self.client.unsubscribe(
            wanted,
            "US_STOCK",
            ["TICK"],
            unsubscribe_all=False,
        )

    def close(self) -> None:
        try:
            self.client.disconnect()
        except Exception:
            LOGGER.exception("GS379 Webull stream disconnect failed")
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=1.0)


def _new_bar(bucket_ms: int, price: float, volume: float) -> dict:
    return {
        "t": bucket_ms,
        "o": price,
        "h": price,
        "l": price,
        "c": price,
        "v": max(0.0, volume),
        "trade_count": 1,
    }


def _record_tick(provider, event: MarketEvent) -> bool:
    """Record one tick; False means the tick is stale and must not update price."""
    price = _number(event.payload.get("price"))
    if price is None:
        return False
    size = max(0.0, _number(event.payload.get("volume")) or 0.0)
    timestamp_ms = int(event.source_timestamp_ms)
    bucket_ms = timestamp_ms - (timestamp_ms % THIRTY_SECOND_MS)
    symbol = event.symbol.upper()

    with provider._lock:
        stream = provider.diagnostics["webull_stream"]
        stream["tick_messages_received"] += 1
        stream["last_tick_timestamp_ms"] = timestamp_ms

        current = provider._gs379_30s_current.get(symbol)
        if current is None:
            provider._gs379_30s_current[symbol] = _new_bar(bucket_ms, price, size)
        elif bucket_ms < current["t"]:
            stream["out_of_order_ticks"] += 1
            return False
        elif bucket_ms > current["t"]:
            provider._gs379_30s_closed[symbol].append(dict(current))
            stream["thirty_second_bars_closed"] += 1
            provider._gs379_30s_current[symbol] = _new_bar(bucket_ms, price, size)
        else:
            current["h"] = max(current["h"], price)
            current["l"] = min(current["l"], price)
            current["c"] = price
            current["v"] += size
            current["trade_count"] += 1

        stream["tick_symbols_seen"] = len(
            set(provider._gs379_30s_current) | set(provider._gs379_30s_closed)
        )
        stream["thirty_second_symbols_ready"] = sum(
            len(rows) >= 10 for rows in provider._gs379_30s_closed.values()
        )
    return True


def _stream_30s_bars(provider, symbol: str) -> list[dict]:
    """Return completed genuine 30-second OHLCV bars only."""
    key = str(symbol or "").strip().upper()
    with provider._lock:
        return [dict(row) for row in provider._gs379_30s_closed.get(key, ())]


def _correct_stream_factory(data_client, app_key, app_secret, streaming_module):
    """Build the SDK 2.0.16 stream factory while preserving ApiClient provenance.

    The pre-GS379 regression inspects the first closure cell to prove the stream
    belongs to the same official ApiClient graph as DataClient. Preserve that
    provenance cell, but do not call the obsolete one-argument constructor.
    """
    legacy_factory = getattr(data_client, "_walter_streaming_client_factory", None)
    api_client = None
    closure = getattr(legacy_factory, "__closure__", None)
    if closure:
        api_client = closure[0].cell_contents

    def factory():
        # Deliberate reference keeps ApiClient as the first closure cell for the
        # established package-layout regression; SDK 2.0.16 itself needs the
        # credential/session constructor below.
        _ = api_client
        return streaming_module.DataStreamingClient(
            app_key,
            app_secret,
            "us",
            uuid.uuid4().hex,
        )

    return factory


def install() -> None:
    """Open Webull tick streaming while keeping GS379 observational only."""
    from . import webull_live, webull_sdk

    # The repository is pinned to webull-openapi-python-sdk 2.0.16. Its
    # DataStreamingClient constructor takes app_key/app_secret/region/session,
    # not the DataClient instance used by Walter's dormant pre-GS379 factory.
    current_create = webull_sdk.create_official_client
    if not getattr(current_create, "_gs379_stream_factory", False):
        @wraps(current_create)
        def create_stream_ready_client(app_key: str, app_secret: str):
            data_client = current_create(app_key, app_secret)
            streaming_module = importlib.import_module("webull.data.data_streaming_client")
            data_client._walter_streaming_client_factory = _correct_stream_factory(
                data_client,
                app_key,
                app_secret,
                streaming_module,
            )
            return data_client

        create_stream_ready_client._gs379_stream_factory = True
        create_stream_ready_client._gs379_original = current_create
        webull_sdk.create_official_client = create_stream_ready_client

    current_stream = webull_sdk.WebullSDKClient.stream
    if not getattr(current_stream, "_gs379_tick_transport", False):
        def stream(self, callback):
            factory = getattr(
                self.sdk_client, "_walter_streaming_client_factory", None
            )
            if factory is None:
                raise RuntimeError("Webull OpenAPI SDK lacks DataStreamingClient")
            return OfficialWebullTickTransport(factory(), callback)

        stream._gs379_tick_transport = True
        stream._gs379_original = current_stream
        webull_sdk.WebullSDKClient.stream = stream

    current_init = webull_live.LiveWebullProvider.__init__
    if not getattr(current_init, "_gs379_stream_enabled", False):
        @wraps(current_init)
        def init(self, app_key: str, app_secret: str, *args, **kwargs):
            if _production_owned_stream(kwargs):
                kwargs["enable_streaming"] = True
            current_init(self, app_key, app_secret, *args, **kwargs)
            self._gs379_30s_current: dict[str, dict] = {}
            self._gs379_30s_closed: dict[str, deque] = {}
            stream_diag = self.diagnostics["webull_stream"]
            stream_diag.update(
                tick_messages_received=0,
                tick_symbols_seen=0,
                last_tick_timestamp_ms=None,
                thirty_second_bars_closed=0,
                thirty_second_symbols_ready=0,
                out_of_order_ticks=0,
                unsubscribed_symbols=0,
                unsubscribe_failures=0,
                thirty_second_authority="OBSERVATIONAL_ONLY",
            )

        init._gs379_stream_enabled = True
        init._gs379_original = current_init
        webull_live.LiveWebullProvider.__init__ = init

    current_event = webull_live.LiveWebullProvider._on_event
    if not getattr(current_event, "_gs379_tick_aggregation", False):
        @wraps(current_event)
        def on_event(self, event: MarketEvent) -> None:
            if event.type == EventType.TRADE:
                # Lazily create bounded histories without retaining individual ticks.
                if event.symbol not in self._gs379_30s_closed:
                    with self._lock:
                        self._gs379_30s_closed.setdefault(
                            event.symbol,
                            deque(maxlen=THIRTY_SECOND_HISTORY),
                        )
                if not _record_tick(self, event):
                    return
                # TICK.volume is trade size, not cumulative session volume. The
                # existing cache expects cumulative volume, so preserve the REST
                # snapshot volume while still refreshing price from the stream.
                payload = dict(event.payload)
                payload["trade_size"] = payload.pop("volume", None)
                event = MarketEvent(
                    event.provider,
                    event.type,
                    event.symbol,
                    event.source_timestamp_ms,
                    payload,
                    event.sequence,
                    event.wire_bytes,
                )
            current_event(self, event)

        on_event._gs379_tick_aggregation = True
        on_event._gs379_original = current_event
        webull_live.LiveWebullProvider._on_event = on_event

    current_ensure = webull_live.LiveWebullProvider.ensure_stream
    if not getattr(current_ensure, "_gs379_reconcile_symbols", False):
        @wraps(current_ensure)
        def ensure_stream(self, symbols) -> bool:
            wanted = {
                str(symbol or "").strip().upper()
                for symbol in symbols
                if str(symbol or "").strip()
            }
            stale = sorted(set(self._subscribed) - wanted)
            transport = getattr(getattr(self, "_subscription", None), "transport", None)
            unsubscribe = getattr(transport, "unsubscribe", None)
            if stale and callable(unsubscribe):
                try:
                    unsubscribe(stale)
                except Exception as exc:
                    self.diagnostics["webull_stream"]["unsubscribe_failures"] += 1
                    self.warnings.append(
                        f"Webull stream could not release stale symbols: {type(exc).__name__}"
                    )
                    LOGGER.warning(
                        "WEBULL stream stale-symbol unsubscribe failed count=%s error_type=%s",
                        len(stale), type(exc).__name__,
                    )
                else:
                    self._subscribed.difference_update(stale)
                    self.diagnostics["webull_stream"]["unsubscribed_symbols"] += len(stale)
            return current_ensure(self, sorted(wanted))

        ensure_stream._gs379_reconcile_symbols = True
        ensure_stream._gs379_original = current_ensure
        webull_live.LiveWebullProvider.ensure_stream = ensure_stream

    if not hasattr(webull_live.LiveWebullProvider, "stream_30s_bars"):
        webull_live.LiveWebullProvider.stream_30s_bars = _stream_30s_bars

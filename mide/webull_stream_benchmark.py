"""Instrumented proof-of-concept harness for Webull streaming market data.

The harness deliberately separates the benchmark from Webull's credential/token
bootstrap.  :class:`PahoWebullStream` consumes broker credentials returned by an
approved OpenAPI application; it never uses consumer cookies or undocumented
endpoints.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import resource
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from threading import Event, Lock
from typing import Callable, Iterable

from .market_data import EventType, MarketDataProvider, MarketEvent
from .market_data_providers import WebullProvider
from .credentials import credential_diagnostics, load_credentials


@dataclass(frozen=True)
class Quote:
    symbol: str
    price: float
    source_timestamp_ms: int
    sequence: int | None = None
    wire_bytes: int = 0
    volume: float | None = None
    bid: float | None = None
    ask: float | None = None


@dataclass
class StageResult:
    requested_symbols: int
    subscribed_symbols: int
    duration_seconds: float
    messages: int
    symbols_updated: int
    latency_p50_ms: float | None
    latency_p95_ms: float | None
    latency_p99_ms: float | None
    cpu_percent: float
    memory_rss_mb: float
    bandwidth_mbps: float
    dropped_messages: int
    sustainable: bool
    failure_reason: str | None = None


def _percentile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    return round(ordered[min(len(ordered) - 1, int((len(ordered) - 1) * fraction))], 3)


class StreamBenchmark:
    """Grow a single connection cumulatively and measure each subscription tier."""

    def __init__(
        self,
        provider_factory: Callable[[Callable[[MarketEvent], None]], MarketDataProvider],
        symbols: Iterable[str],
        *,
        duration_seconds: float = 60,
        max_p95_latency_ms: float = 1_000,
        min_coverage: float = 0.0,
    ):
        self.provider_factory = provider_factory
        self.symbols = list(dict.fromkeys(s.strip().upper() for s in symbols if s.strip()))
        self.duration_seconds = duration_seconds
        self.max_p95_latency_ms = max_p95_latency_ms
        self.min_coverage = min_coverage
        self.cache: dict[str, Quote] = {}
        self._lock = Lock()
        self._latencies: list[float] = []
        self._messages = self._bytes = self._drops = 0
        self._last_sequence: dict[str, int] = {}

    def _on_event(self, event: MarketEvent) -> None:
        quote = Quote(event.symbol, float(event.payload["price"]), event.source_timestamp_ms,
                      event.sequence, event.wire_bytes)
        now_ms = time.time_ns() / 1_000_000
        with self._lock:
            self.cache[quote.symbol] = quote
            self._latencies.append(max(0.0, now_ms - quote.source_timestamp_ms))
            self._messages += 1
            self._bytes += quote.wire_bytes
            if quote.sequence is not None:
                previous = self._last_sequence.get(quote.symbol)
                if previous is not None and quote.sequence > previous + 1:
                    self._drops += quote.sequence - previous - 1
                self._last_sequence[quote.symbol] = quote.sequence

    def run(self, tiers: Iterable[int] = (100, 500, 2_000)) -> list[StageResult]:
        if not self.symbols:
            raise ValueError("the symbol universe is empty")
        targets = list(dict.fromkeys([*tiers, len(self.symbols)]))
        targets = [min(value, len(self.symbols)) for value in targets if value > 0]
        targets = list(dict.fromkeys(targets))
        provider = self.provider_factory(self._on_event)
        results: list[StageResult] = []
        subscribed = 0
        subscription = provider.subscribe([], (EventType.QUOTE, EventType.TRADE), self._on_event)
        try:
            for target in targets:
                result, subscribed = self._run_stage(subscription, target, subscribed)
                results.append(result)
                if not result.sustainable:
                    break
        finally:
            subscription.close()
        return results

    def _run_stage(self, subscription, target: int, subscribed: int) -> tuple[StageResult, int]:
        start_messages, start_bytes, start_drops = self._messages, self._bytes, self._drops
        start_cpu, started = time.process_time(), time.monotonic()
        existing_cache = set(self.cache)
        failure = None
        try:
            subscription.add(self.symbols[subscribed:target])
            subscribed = target
            Event().wait(self.duration_seconds)
        except Exception as exc:  # transport failures are benchmark results
            failure = f"{type(exc).__name__}: {exc}"
        elapsed = max(time.monotonic() - started, 1e-9)
        with self._lock:
            latencies = self._latencies[:]
            self._latencies.clear()
            messages = self._messages - start_messages
            wire_bytes = self._bytes - start_bytes
            drops = self._drops - start_drops
            updated = len(set(self.cache) - existing_cache)
        p95 = _percentile(latencies, 0.95)
        coverage = updated / target if target else 0
        sustainable = failure is None and (p95 is None or p95 <= self.max_p95_latency_ms)
        sustainable = sustainable and coverage >= self.min_coverage
        if failure is None and not sustainable:
            failure = f"threshold exceeded (p95={p95}, coverage={coverage:.1%})"
        usage = resource.getrusage(resource.RUSAGE_SELF)
        rss_mb = usage.ru_maxrss / (1024 if os.name != "darwin" else 1024 * 1024)
        return StageResult(
            requested_symbols=target, subscribed_symbols=subscribed, duration_seconds=round(elapsed, 3),
            messages=messages, symbols_updated=updated, latency_p50_ms=_percentile(latencies, .50),
            latency_p95_ms=p95, latency_p99_ms=_percentile(latencies, .99),
            cpu_percent=round(100 * (time.process_time() - start_cpu) / elapsed, 2),
            memory_rss_mb=round(rss_mb, 2), bandwidth_mbps=round(wire_bytes * 8 / elapsed / 1_000_000, 4),
            dropped_messages=drops, sustainable=sustainable, failure_reason=failure,
        ), subscribed


class PahoWebullStream:
    """MQTT-over-WebSocket transport configured from OpenAPI-issued credentials."""

    def __init__(self, on_event: Callable[[MarketEvent], None], *, host: str, port: int,
                 username: str, password: str, topic_template: str, client_id: str,
                 parser: Callable[[bytes], Quote], on_disconnect: Callable[[], None] | None = None):
        try:
            import paho.mqtt.client as mqtt
        except ImportError as exc:
            raise RuntimeError("install paho-mqtt to run the live benchmark") from exc
        self._on_event, self._parser, self._topic_template = on_event, parser, topic_template
        self._host, self._port = host, port
        self._connected = Event()
        self._client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=client_id,
                                   transport="websockets")
        self._client.username_pw_set(username, password)
        self._client.tls_set()
        self._client.on_connect = self._handle_connect
        self._client.on_message = self._handle_message
        self._disconnect_callback = on_disconnect
        self._client.on_disconnect = self._handle_disconnect

    def _handle_connect(self, client, userdata, flags, reason_code, properties) -> None:
        if reason_code == 0:
            self._connected.set()

    def _handle_message(self, client, userdata, message) -> None:
        quote = self._parser(message.payload)
        self._on_event(MarketEvent("Webull OpenAPI", EventType.TRADE, quote.symbol,
            quote.source_timestamp_ms, {"price": quote.price, "volume": quote.volume,
            "bid": quote.bid, "ask": quote.ask}, quote.sequence, len(message.payload)))

    def _handle_disconnect(self, client, userdata, disconnect_flags, reason_code, properties) -> None:
        self._connected.clear()
        if self._disconnect_callback:
            self._disconnect_callback()

    def connect(self) -> None:
        self._client.connect(self._host, self._port, keepalive=30)
        self._client.loop_start()
        if not self._connected.wait(8):
            self._client.disconnect()
            self._client.loop_stop()
            raise TimeoutError("Webull MQTT authentication did not complete within 8 seconds")

    def subscribe(self, symbols: list[str]) -> None:
        for symbol in symbols:
            result, _ = self._client.subscribe(self._topic_template.format(symbol=symbol), qos=1)
            if result != 0:
                raise RuntimeError(f"MQTT rejected subscription for {symbol}: code {result}")

    def close(self) -> None:
        self._client.disconnect()
        self._client.loop_stop()


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark an approved Webull OpenAPI MQTT stream")
    parser.add_argument("symbols", type=Path, help="newline-delimited Webull instrument identifiers")
    parser.add_argument("--duration", type=float, default=60)
    parser.add_argument("--output", type=Path, default=Path("webull-stream-results.json"))
    args = parser.parse_args()
    required = ("WEBULL_MQTT_HOST", "WEBULL_MQTT_USERNAME", "WEBULL_MQTT_PASSWORD",
                "WEBULL_MQTT_CLIENT_ID", "WEBULL_MQTT_TOPIC_TEMPLATE")
    credentials = load_credentials(required)
    for diagnostic in credential_diagnostics(credentials):
        print(f"Webull credential startup check: {diagnostic}", file=sys.stderr)
    missing = [name for name, credential in credentials.items() if not credential.present]
    if missing:
        parser.error("missing OpenAPI bootstrap values: " + ", ".join(missing))

    def parse_quote(payload: bytes) -> Quote:
        data = json.loads(payload)
        return Quote(str(data["symbol"]), float(data["price"]), int(data["timestamp_ms"]),
                     int(data["sequence"]) if data.get("sequence") is not None else None)

    def factory(callback):
        def stream_factory(receive):
            return PahoWebullStream(receive, host=credentials["WEBULL_MQTT_HOST"].value,
            port=int(os.getenv("WEBULL_MQTT_PORT", "443")), username=credentials["WEBULL_MQTT_USERNAME"].value,
            password=credentials["WEBULL_MQTT_PASSWORD"].value, client_id=credentials["WEBULL_MQTT_CLIENT_ID"].value,
            topic_template=credentials["WEBULL_MQTT_TOPIC_TEMPLATE"].value, parser=parse_quote)
        return WebullProvider(stream_factory=stream_factory)

    benchmark = StreamBenchmark(factory, args.symbols.read_text().splitlines(), duration_seconds=args.duration)
    results = [asdict(result) for result in benchmark.run()]
    args.output.write_text(json.dumps({"results": results, "cache_size": len(benchmark.cache)}, indent=2) + "\n")
    return 0 if results and results[-1]["sustainable"] else 2


if __name__ == "__main__":
    raise SystemExit(main())

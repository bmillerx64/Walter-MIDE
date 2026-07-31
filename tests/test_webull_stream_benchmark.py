import time

from mide.market_data import EventType, MarketEvent
from mide.webull_stream_benchmark import StreamBenchmark


class FakeStream:
    def __init__(self, callback):
        self.subscriptions = []
        self.closed = False

    def connect(self):
        pass

    def subscribe(self, symbols):
        self.subscriptions.append(list(symbols))
        for symbol in symbols:
            now = int(time.time_ns() / 1_000_000)
            self.callback(MarketEvent("Fake", EventType.TRADE, symbol, now, {"price": 10.0}, 1, 100))
            self.callback(MarketEvent("Fake", EventType.TRADE, symbol, now, {"price": 10.1}, 3, 100))

    def close(self):
        self.closed = True


class FakeProvider:
    def __init__(self, callback, stream_class=FakeStream):
        self.stream = stream_class(callback)

    def subscribe(self, symbols, event_types, handler):
        self.stream.callback = handler
        self.stream.connect()
        wanted = list(symbols)
        if wanted:
            self.stream.subscribe(wanted)
        return FakeSubscription(self.stream)


class FakeSubscription:
    def __init__(self, stream):
        self.stream = stream

    def add(self, symbols):
        self.stream.subscribe(symbols)

    def close(self):
        self.stream.close()


def test_benchmark_grows_subscription_and_measures_gaps():
    streams = []

    def factory(callback):
        provider = FakeProvider(callback)
        streams.append(provider.stream)
        return provider

    benchmark = StreamBenchmark(factory, (f"S{i}" for i in range(5)), duration_seconds=0,
                                max_p95_latency_ms=1000)
    results = benchmark.run((2, 4))

    assert [r.requested_symbols for r in results] == [2, 4, 5]
    assert streams[0].subscriptions == [["S0", "S1"], ["S2", "S3"], ["S4"]]
    assert [r.messages for r in results] == [4, 4, 2]
    assert [r.dropped_messages for r in results] == [2, 2, 1]
    assert len(benchmark.cache) == 5
    assert all(r.sustainable for r in results)
    assert streams[0].closed


def test_benchmark_stops_after_subscription_failure():
    class Broken(FakeStream):
        def subscribe(self, symbols):
            raise RuntimeError("vendor limit")

    result = StreamBenchmark(lambda callback: FakeProvider(callback, Broken), ["AAA"],
                             duration_seconds=0).run()[0]
    assert not result.sustainable
    assert result.failure_reason == "RuntimeError: vendor limit"

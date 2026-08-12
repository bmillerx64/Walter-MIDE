from threading import Lock
from types import MethodType

from mide.webull_connection import _fresh_live_webull_snapshots
from mide.webull_live import CachedMarketData, LiveWebullProvider


def _provider(*, streaming=False):
    provider = object.__new__(LiveWebullProvider)
    provider._enable_streaming = streaming
    provider._lock = Lock()
    provider.cache = {}
    provider._snapshot_cache = {}
    provider.diagnostics = {"webull_stream": {}}
    provider.warnings = []
    provider.refresh_calls = 0

    def initialize_quotes(self, symbols):
        self.refresh_calls += 1
        volume = 100_000 * self.refresh_calls
        for symbol in symbols:
            self._snapshot_cache[symbol] = {
                "latestTrade": {"p": 1.0},
                "dailyBar": {"c": 1.0, "v": volume},
                "prevDailyBar": {"c": 0.5},
            }
            self.cache[symbol] = CachedMarketData(
                price=1.0,
                volume=volume,
                bid=0.99,
                ask=1.01,
                source_timestamp_ms=1,
                received_timestamp_ms=1,
            )
        return {symbol: 1.0 for symbol in symbols}

    provider.initialize_quotes = MethodType(initialize_quotes, provider)
    return provider


def test_snapshot_only_mode_refreshes_every_explicit_scan():
    provider = _provider(streaming=False)

    first = provider.snapshots(["TEST"])
    second = provider.snapshots(["TEST"])

    assert provider.refresh_calls == 2
    assert first["TEST"]["dailyBar"]["v"] == 100_000
    assert second["TEST"]["dailyBar"]["v"] == 200_000
    assert provider.diagnostics["webull_stream"]["snapshot_refresh_mode"] == "rest_each_scan"


def test_streaming_mode_keeps_stream_cache_without_forced_rest_refresh():
    provider = _provider(streaming=True)
    provider.initialize_quotes(["TEST"])
    provider.refresh_calls = 0

    snapshot = provider.snapshots(["TEST"])

    assert provider.refresh_calls == 0
    assert snapshot["TEST"]["dailyBar"]["v"] == 100_000


def test_refresh_wrapper_normalizes_duplicate_symbols_before_rest_call():
    provider = _provider(streaming=False)

    _fresh_live_webull_snapshots(provider, [" test ", "TEST", ""])

    assert provider.refresh_calls == 1
    assert provider.diagnostics["webull_stream"]["snapshot_refresh_symbols"] == 1

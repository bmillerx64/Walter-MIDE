import inspect
import time

import pytest

from mide.market_data import EventType, MarketEvent
from mide.webull_connection import run_connection_test
from mide.webull_live import LiveWebullProvider, WebullOpenAPIClient, live_data_modes
from mide.webull_sdk import WebullSDKClient


class Rest:
    def __init__(self):
        self.calls = []

    def snapshots(self, symbols):
        self.calls.append(list(symbols))
        return {symbol: {"latestTrade": {"p": 10.0}, "dailyBar": {"v": 50}}
                for symbol in symbols}


class Universe:
    def assets(self):
        return [{"symbol": "AAA", "tradable": True}]


class Bootstrap:
    def obtain(self):
        return {"host": "stream.test", "port": 443, "username": "user", "password": "token",
                "client_id": "walter", "topic_template": "quotes/{symbol}"}


class Stream:
    def __init__(self, callback, **kwargs): self.callback = callback
    def connect(self): pass
    def subscribe(self, symbols):
        for symbol in symbols:
            self.callback(MarketEvent("Webull OpenAPI SDK", EventType.TRADE, symbol,
                time.time_ns() // 1_000_000, {"price": 12.5, "volume": 100}))
    def close(self): pass


def test_provider_selection_prefers_configured_webull():
    assert live_data_modes(alpaca_configured=True, webull_configured=True)[1] == 1


def test_official_sdk_client_is_selected_and_handwritten_auth_is_absent():
    source = inspect.getsource(__import__("mide.webull_live", fromlist=["x"]))
    assert "hmac.new" not in source
    assert "x-signature" not in source
    sdk = object()
    client = WebullOpenAPIClient("key", "secret", sdk_client=sdk)
    assert isinstance(client.sdk, WebullSDKClient)
    assert client.sdk.sdk_client is sdk


def test_sdk_snapshot_arguments_and_normalization():
    class SDK:
        def get_stock_snapshot(self, **kwargs):
            assert kwargs == {"symbols": "HYFM", "category": "US_STOCK",
                              "extend_hour_required": True, "overnight_required": True}
            return {"data": [{"symbol": "HYFM", "last_price": "3.25", "volume": 9}]}
    result = WebullOpenAPIClient("k", "s", sdk_client=SDK()).snapshots(["HYFM"])
    assert result["HYFM"]["latestTrade"]["p"] == 3.25


def test_snapshot_batches_never_exceed_100_symbols():
    rest = Rest()
    provider = LiveWebullProvider("key", "secret", rest_client=rest,
        universe_client=Universe(), bootstrap=Bootstrap(), stream_class=Stream)
    symbols = [f"S{i}" for i in range(251)]
    provider.initialize_quotes(symbols, batch_size=500)
    assert [len(call) for call in rest.calls] == [100, 100, 51]


def test_provider_diagnostics_are_accurate():
    provider = LiveWebullProvider("key", "secret", rest_client=Rest(),
        universe_client=Universe(), bootstrap=Bootstrap(), stream_class=Stream)
    assert provider.diagnostics["market_data_sources"] == {
        "universe_provider": "Alpaca Trading API",
        "quote_provider": "Webull OpenAPI SDK",
        "bars_provider": "Webull OpenAPI SDK",
        "streaming_provider": "Webull OpenAPI SDK",
    }
    sources = {row["Stage"]: row for row in provider.pipeline_sources()}
    assert sources["Universe (tradable symbol list)"]["Endpoint / operation"] == "GET /v2/assets (symbol master only)"
    assert "stock/snapshot" in sources["Quote / snapshot retrieval"]["Endpoint / operation"]


def test_sdk_failure_surfaces_visibly_in_connection_test():
    class Broken:
        def __init__(self, *_): pass
        def snapshots(self, symbols): raise PermissionError("entitlement denied")
    rows = run_connection_test(app_key="key", app_secret="secret",
        eligible_symbols=[f"S{i}" for i in range(100)], client_factory=Broken)
    hyfm = next(row for row in rows if row["Test"] == "HYFM snapshot")
    assert hyfm["Status"] == "FAIL"
    assert hyfm["Actual exception / API error"] == "PermissionError: entitlement denied"
    assert hyfm["Endpoint / SDK operation"].endswith("/stock/snapshot")


def test_connection_test_batches_full_universe_at_100():
    calls = []
    class Mock:
        def __init__(self, *_): pass
        def snapshots(self, symbols):
            calls.append(list(symbols)); return {s: {} for s in symbols}
    rows = run_connection_test(app_key="key", app_secret="secret",
        eligible_symbols=[f"S{i}" for i in range(205)], client_factory=Mock)
    full = next(row for row in rows if row["Test"] == "Full eligible-universe batching")
    assert full["Status"] == "PASS"
    assert full["Request count"] == 3
    assert max(map(len, calls)) <= 100

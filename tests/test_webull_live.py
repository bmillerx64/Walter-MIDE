import json
import time

from mide.market_data import EventType, MarketEvent
from mide.webull_live import (LiveWebullProvider, WebullBootstrap,
                              WebullOpenAPIClient, live_data_modes)


class Fallback:
    warnings = []

    def __init__(self):
        self.warnings = []
        self.diagnostics = {}

    def latest_trades(self, symbols):
        return {symbol: 1.0 for symbol in symbols}

    def snapshots(self, symbols):
        return {symbol: {"latestTrade": {"p": 1.0}, "dailyBar": {"v": 5}} for symbol in symbols}

    def news(self, *args, **kwargs):
        return []


class Bootstrap:
    def obtain(self):
        return {"host": "stream.test", "port": 443, "username": "user", "password": "token",
                "client_id": "walter", "topic_template": "quotes/{symbol}"}


class Rest:
    def snapshots(self, symbols):
        return {symbol: {"latestTrade": {"p": 10.0}, "dailyBar": {"v": 50}}
                for symbol in symbols}


class Stream:
    def __init__(self, callback, **kwargs):
        self.callback = callback

    def connect(self):
        pass

    def subscribe(self, symbols):
        for symbol in symbols:
            self.callback(MarketEvent("Webull OpenAPI", EventType.TRADE, symbol,
                time.time_ns() // 1_000_000, {"price": 12.5, "volume": 100, "bid": 12.4, "ask": 12.6}))

    def close(self):
        pass


def test_provider_selection_includes_webull_and_prefers_configured_provider():
    assert live_data_modes(alpaca_configured=True, webull_configured=True) == (
        ["Live Alpaca", "Live Webull", "Demo"], 1)
    assert live_data_modes(alpaca_configured=True, webull_configured=False)[1] == 0
    assert live_data_modes(alpaca_configured=False, webull_configured=True)[1] == 1
    assert live_data_modes(alpaca_configured=False, webull_configured=False)[1] == 2


def test_webull_stream_cache_is_webull_only():
    provider = LiveWebullProvider("key", "secret",
                                  bootstrap=Bootstrap(), rest_client=Rest(), stream_class=Stream)
    prices = provider.latest_trades(["AAA"])
    snapshots = provider.snapshots(["AAA"])

    assert prices == {"AAA": 12.5}
    assert snapshots["AAA"]["latestTrade"]["p"] == 12.5
    assert snapshots["AAA"]["dailyBar"]["v"] == 100
    assert snapshots["AAA"]["market_data_provider"] == "Webull OpenAPI streaming cache"
    assert provider.diagnostics["webull_stream"]["messages_received"] == 1
    assert provider.diagnostics["webull_stream"]["cached_symbols"] == 1


def test_webull_initialization_failure_retains_webull_snapshot_and_reports_error():
    class BrokenBootstrap:
        def obtain(self):
            raise RuntimeError("denied")

    provider = LiveWebullProvider("key", "secret",
                                  bootstrap=BrokenBootstrap(), rest_client=Rest(), stream_class=Stream)

    assert provider.latest_trades(["AAA"]) == {"AAA": 10.0}
    diagnostics = provider.diagnostics["webull_stream"]
    assert diagnostics["authentication_status"] == "failed"
    assert diagnostics["stream_connection_status"] == "error"
    assert diagnostics["subscription_failures"] == ["RuntimeError: denied"]
    assert "cached Webull snapshot retained" in provider.warnings[-1]


def test_snapshot_is_complete_before_stream_starts_and_no_alpaca_prices_are_polled():
    order = []

    class OrderedRest:
        def snapshots(self, symbols):
            order.append(("snapshot", tuple(symbols)))
            return Rest().snapshots(symbols)

    class OrderedStream(Stream):
        def connect(self):
            order.append(("stream",))

    provider = LiveWebullProvider("key", "secret",
        bootstrap=Bootstrap(), rest_client=OrderedRest(), stream_class=OrderedStream)

    assert provider.initialize_quotes(["AAA", "BBB"]) == {"AAA": 12.5, "BBB": 12.5}
    assert order[0][0] == "snapshot"
    assert order[1][0] == "stream"
    diagnostics = provider.diagnostics["webull_stream"]
    assert diagnostics["symbols_missing_prices"] == 0
    assert provider.diagnostics["market_data_sources"] == {
        "universe_provider": "Webull OpenAPI stock rankings",
        "snapshot_provider": "Webull OpenAPI",
        "streaming_provider": "Webull OpenAPI",
    }

    sources = {row["Stage"]: row for row in provider.pipeline_sources()}
    assert sources["Universe (tradable symbol list)"]["Actual provider"] == "Webull OpenAPI rankings"
    assert "/market-data/stock-rank/list" in sources["Universe (tradable symbol list)"]["Endpoint / operation"]
    assert sources["Quote / snapshot retrieval"]["Actual provider"] == "Webull OpenAPI"
    assert "/market-data/quotes" in sources["Quote / snapshot retrieval"]["Endpoint / operation"]
    assert sources["News"]["Alpaca used"] == "No"
    assert "no raw article feed" in sources["News"]["Endpoint / operation"]
    assert sources["VWAP / volume calculations"]["Alpaca used"] == "No"
    assert "/market-data/history" in sources["VWAP / volume calculations"]["Endpoint / operation"]
    assert sources["Scanning / filtering"]["Endpoint / operation"].startswith("No provider endpoint")


def test_official_snapshot_client_signs_request_and_normalizes_quotes():
    captured = {}

    class Response:
        def raise_for_status(self): pass
        def json(self):
            return {"data": [{"symbol": "AAA", "last_price": "7.25", "volume": 99}]}

    class Session:
        @staticmethod
        def get(url, **kwargs):
            captured.update(url=url, **kwargs)
            return Response()

    snapshots = WebullOpenAPIClient("app-key", "secret", base_url="https://example.test",
                                    session=Session).snapshots(["AAA"])
    assert snapshots["AAA"]["latestTrade"]["p"] == 7.25
    assert "symbols=AAA" in captured["url"]
    assert captured["headers"]["x-app-key"] == "app-key"
    assert "secret" not in json.dumps(captured)


def test_bootstrap_never_places_secret_in_request(monkeypatch):
    captured = {}

    class Response:
        def raise_for_status(self):
            pass

        def json(self):
            return {"host": "h", "username": "u", "password": "p", "client_id": "c"}

    class Session:
        @staticmethod
        def post(url, **kwargs):
            captured.update(kwargs)
            return Response()

    result = WebullBootstrap("app-key", "top-secret", session=Session).obtain()
    serialized = json.dumps(captured)
    assert "top-secret" not in serialized
    assert captured["headers"]["x-app-key"] == "app-key"
    assert result["password"] == "p"


def test_live_webull_scan_guard_forbids_alpaca_import_or_api_call(monkeypatch):
    """Regression guard for the complete Live Webull market-data path."""
    import builtins
    from datetime import datetime, timezone

    real_import = builtins.__import__
    calls = []

    def guarded_import(name, *args, **kwargs):
        if name == "mide.alpaca" or name.endswith(".alpaca"):
            raise AssertionError("Live Webull attempted to import Alpaca")
        return real_import(name, *args, **kwargs)

    class CompleteRest(Rest):
        def assets(self):
            calls.append("webull-universe")
            return [{"symbol": "AAA", "tradable": True}]

        def bars(self, symbols, **kwargs):
            calls.append("webull-bars")
            return {symbol: [] for symbol in symbols}

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    provider = LiveWebullProvider("key", "secret", bootstrap=Bootstrap(),
                                  rest_client=CompleteRest(), stream_class=Stream)
    assert provider.assets()[0]["symbol"] == "AAA"
    assert provider.initialize_quotes(["AAA"]) == {"AAA": 12.5}
    assert provider.bars(["AAA"], start=datetime.now(timezone.utc))["AAA"] == []
    assert provider.news(datetime.now(timezone.utc)) == []
    assert calls == ["webull-universe", "webull-bars"]
    assert all(row["Alpaca used"] == "No" for row in provider.pipeline_sources())

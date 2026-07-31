import json
import time

from mide.market_data import EventType, MarketEvent
from mide.webull_live import LiveWebullProvider, WebullBootstrap, live_data_modes


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
        ["Live Alpaca", "Live Webull", "Demo"], 0)
    assert live_data_modes(alpaca_configured=False, webull_configured=True)[1] == 1
    assert live_data_modes(alpaca_configured=False, webull_configured=False)[1] == 2


def test_webull_stream_cache_overlays_alpaca_fallback():
    provider = LiveWebullProvider("key", "secret", fallback=Fallback(),
                                  bootstrap=Bootstrap(), stream_class=Stream)
    prices = provider.latest_trades(["AAA"])
    snapshots = provider.snapshots(["AAA"])

    assert prices == {"AAA": 12.5}
    assert snapshots["AAA"]["latestTrade"]["p"] == 12.5
    assert snapshots["AAA"]["dailyBar"]["v"] == 100
    assert snapshots["AAA"]["market_data_provider"] == "Webull OpenAPI streaming cache"
    assert provider.diagnostics["webull_stream"]["messages_received"] == 1
    assert provider.diagnostics["webull_stream"]["cached_symbols"] == 1


def test_webull_initialization_failure_retains_alpaca_data_and_reports_error():
    class BrokenBootstrap:
        def obtain(self):
            raise RuntimeError("denied")

    fallback = Fallback()
    provider = LiveWebullProvider("key", "secret", fallback=fallback,
                                  bootstrap=BrokenBootstrap(), stream_class=Stream)

    assert provider.latest_trades(["AAA"]) == {"AAA": 1.0}
    diagnostics = provider.diagnostics["webull_stream"]
    assert diagnostics["authentication_status"] == "failed"
    assert diagnostics["stream_connection_status"] == "error"
    assert diagnostics["subscription_failures"] == ["RuntimeError: denied"]
    assert "using Alpaca fallback" in fallback.warnings[-1]


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

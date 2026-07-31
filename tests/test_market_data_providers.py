from datetime import datetime, timezone

import pytest

from mide.market_data import EventType, MarketDataProvider, MarketEvent
from mide.market_data_providers import AlpacaProvider, WebullProvider


class StubAlpaca:
    provider_name = "Alpaca Market Data"
    diagnostics = {}
    warnings = []

    def snapshots(self, symbols):
        return {symbol: {"latestQuote": {"bp": 1, "ap": 2}} for symbol in symbols}

    def latest_trades(self, symbols):
        return {symbol: 1.5 for symbol in symbols}

    def news(self, start, limit, **kwargs):
        return [{"headline": "official"}]


def test_alpaca_fallback_implements_provider_contract():
    provider = AlpacaProvider(client=StubAlpaca())
    assert isinstance(provider, MarketDataProvider)
    assert provider.quotes(["AAA"]) == {"AAA": {"bp": 1, "ap": 2}}
    assert provider.trades(["AAA"]) == {"AAA": 1.5}
    assert provider.latest_trades(["AAA"]) == {"AAA": 1.5}
    assert provider.news(datetime.now(timezone.utc)) == [{"headline": "official"}]
    with pytest.raises(NotImplementedError, match="streaming is not configured"):
        provider.subscribe([], [EventType.TRADE], lambda event: None).add(["AAA"])


class FakeTransport:
    def __init__(self, callback):
        self.callback = callback
        self.connected = False
        self.added = []
        self.closed = False

    def connect(self):
        self.connected = True

    def subscribe(self, symbols):
        self.added.append(list(symbols))
        for symbol in symbols:
            self.callback(MarketEvent("Webull OpenAPI", EventType.TRADE, symbol, 1,
                                      {"price": 12.5}, 7, 80))

    def close(self):
        self.closed = True


def test_webull_stream_is_only_consumed_through_provider_contract():
    transports, events = [], []

    def factory(callback):
        transports.append(FakeTransport(callback))
        return transports[-1]

    provider = WebullProvider(stream_factory=factory)
    subscription = provider.subscribe(["AAA"], [EventType.TRADE], events.append)
    subscription.add(["BBB"])
    subscription.close()

    assert transports[0].connected
    assert transports[0].added == [["AAA"], ["BBB"]]
    assert [event.symbol for event in events] == ["AAA", "BBB"]
    assert transports[0].closed


def test_webull_rest_operations_use_official_sdk_adapter():
    class Rest:
        def snapshots(self, symbols):
            return {symbols[0]: {"latestTrade": {"p": 4}}}

    provider = WebullProvider(rest_client=Rest())
    assert provider.snapshots(["AAA"])["AAA"]["latestTrade"]["p"] == 4
    with pytest.raises(NotImplementedError, match="does not implement quotes"):
        provider.quotes(["AAA"])


def test_intelligence_layers_do_not_import_vendor_adapters():
    from pathlib import Path

    for module in ("indicators.py", "conviction.py", "scanner_v2.py", "escalation.py"):
        source = (Path(__file__).parents[1] / "mide" / module).read_text()
        assert "mide.alpaca" not in source
        assert "mide.market_data_providers" not in source
        assert "webull" not in source.casefold()

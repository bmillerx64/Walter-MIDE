from threading import Event

from mide import gs379_webull_stream_data_truth as gs379
from mide.market_data import EventType, MarketEvent
from mide.webull_live import LiveWebullProvider
from mide import webull_sdk


class _Basic:
    symbol = "OLOX"
    timestamp = 1_788_500_000_123


class _Tick:
    basic = _Basic()
    price = "1.2345"
    volume = "250"
    side = "BUY"


def test_official_tick_result_normalizes_to_walter_trade_event():
    event = gs379._tick_market_event(_Tick())

    assert event is not None
    assert event.provider == "Webull OpenAPI"
    assert event.type == EventType.TRADE
    assert event.symbol == "OLOX"
    assert event.source_timestamp_ms == _Basic.timestamp
    assert event.payload == {
        "price": 1.2345,
        "volume": 250.0,
        "side": "BUY",
        "stream_payload": "TICK",
    }


class _StreamingClient:
    def __init__(self):
        self.on_connect_success = None
        self.on_quotes_message = None
        self.on_subscribe_success = None
        self.subscriptions = []
        self.disconnected = False
        self.stop = Event()

    def connect_and_loop_forever(self, logger_enable=True):
        assert logger_enable is False
        self.on_connect_success(self, object(), "session")
        self.stop.wait(1)

    def subscribe(self, symbols, category, sub_types):
        self.subscriptions.append((list(symbols), category, list(sub_types)))
        self.on_subscribe_success(self, object(), "session")
        self.on_quotes_message(self, "tick", _Tick())

    def disconnect(self):
        self.disconnected = True
        self.stop.set()


def test_official_transport_subscribes_only_to_us_stock_ticks():
    client = _StreamingClient()
    events = []
    transport = gs379.OfficialWebullTickTransport(client, events.append)

    transport.connect()
    transport.subscribe(["olox", "OLOX", "GRI"])
    transport.close()

    assert client.subscriptions == [(["OLOX", "GRI"], "US_STOCK", ["TICK"])]
    assert len(events) == 1
    assert events[0].symbol == "OLOX"
    assert client.disconnected is True


def test_only_real_sdk_owned_provider_auto_opens_streaming():
    assert gs379._production_owned_stream({}) is True
    assert gs379._production_owned_stream({"universe_client": object()}) is True
    assert gs379._production_owned_stream({"enable_streaming": False}) is False
    assert gs379._production_owned_stream({"rest_client": object()}) is False
    assert gs379._production_owned_stream({"stream_class": object()}) is False
    assert gs379._production_owned_stream({"sdk_client": object()}) is False


class _Rest:
    def snapshots(self, symbols):
        return {
            symbol: {
                "latestTrade": {"p": 1.00, "t": 1_788_500_000_000},
                "latestQuote": {"bp": 0.99, "ap": 1.01},
                "dailyBar": {"c": 1.00, "v": 1_000_000},
                "prevDailyBar": {"c": 0.90, "v": 500_000},
                "market_data_provider": "Webull OpenAPI SDK",
            }
            for symbol in symbols
        }


def _trade(symbol, timestamp_ms, price, size):
    return MarketEvent(
        "Webull OpenAPI",
        EventType.TRADE,
        symbol,
        timestamp_ms,
        {"price": price, "volume": size, "stream_payload": "TICK"},
    )


def test_tick_stream_builds_closed_30s_bars_without_corrupting_session_volume():
    provider = LiveWebullProvider(
        "key",
        "secret",
        rest_client=_Rest(),
        enable_streaming=False,
    )
    provider.initialize_quotes(["OLOX"])
    assert provider.cache["OLOX"].volume == 1_000_000

    start = 1_788_500_010_000
    provider._on_event(_trade("OLOX", start, 1.00, 100))
    provider._on_event(_trade("OLOX", start + 5_000, 1.05, 150))
    # Next 30-second bucket closes the first bar.
    provider._on_event(_trade("OLOX", start + 35_000, 1.03, 200))

    bars = provider.stream_30s_bars("OLOX")
    assert len(bars) == 1
    assert bars[0]["o"] == 1.00
    assert bars[0]["h"] == 1.05
    assert bars[0]["l"] == 1.00
    assert bars[0]["c"] == 1.05
    assert bars[0]["v"] == 250
    assert bars[0]["trade_count"] == 2

    # TICK volume is transaction size; Walter's session-volume cache must keep
    # the cumulative REST snapshot volume instead of dropping to 200 shares.
    assert provider.cache["OLOX"].volume == 1_000_000
    assert provider.cache["OLOX"].price == 1.03
    diagnostics = provider.diagnostics["webull_stream"]
    assert diagnostics["tick_messages_received"] == 3
    assert diagnostics["thirty_second_bars_closed"] == 1
    assert diagnostics["thirty_second_authority"] == "OBSERVATIONAL_ONLY"


def test_out_of_order_tick_is_observed_but_cannot_rewrite_closed_sequence():
    provider = LiveWebullProvider(
        "key",
        "secret",
        rest_client=_Rest(),
        enable_streaming=False,
    )
    provider.initialize_quotes(["OLOX"])
    start = 1_788_500_010_000
    provider._on_event(_trade("OLOX", start + 35_000, 1.03, 200))
    provider._on_event(_trade("OLOX", start, 0.98, 500))

    assert provider.diagnostics["webull_stream"]["out_of_order_ticks"] == 1
    assert provider.stream_30s_bars("OLOX") == []


def test_runtime_hooks_are_installed_without_changing_sdk_pin_contract():
    assert getattr(webull_sdk.create_official_client, "_gs379_stream_factory", False)
    assert getattr(webull_sdk.WebullSDKClient.stream, "_gs379_tick_transport", False)
    assert getattr(LiveWebullProvider.__init__, "_gs379_stream_enabled", False)
    assert getattr(LiveWebullProvider._on_event, "_gs379_tick_aggregation", False)
    assert hasattr(LiveWebullProvider, "stream_30s_bars")

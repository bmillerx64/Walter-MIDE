import inspect
import sys
import time
import types

import pytest

from mide.market_data import EventType, MarketEvent
from mide.webull_connection import run_connection_test
from mide.webull_live import LiveWebullProvider, WebullOpenAPIClient, live_data_modes
from mide.webull_sdk import TracedHTTPTransport, WebullSDKClient, create_official_client


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


def test_official_sdk_uses_installed_package_layout(monkeypatch, tmp_path):
    calls = []

    class ApiClient:
        def __init__(self, **kwargs):
            calls.append(("ApiClient", kwargs))

    class MarketDataApi:
        def __init__(self, api_client):
            calls.append(("MarketDataApi", api_client))
            self.api_client = api_client

    core = types.ModuleType("webullsdkcore")
    core.__path__ = []
    core_client = types.ModuleType("webullsdkcore.client")
    core_client.ApiClient = ApiClient
    mdata = types.ModuleType("webullsdkmdata")
    mdata.__path__ = []
    mdata_api = types.ModuleType("webullsdkmdata.api")
    mdata_api.MarketDataApi = MarketDataApi
    monkeypatch.setitem(sys.modules, "webullsdkcore", core)
    monkeypatch.setitem(sys.modules, "webullsdkcore.client", core_client)
    monkeypatch.setitem(sys.modules, "webullsdkmdata", mdata)
    monkeypatch.setitem(sys.modules, "webullsdkmdata.api", mdata_api)

    (tmp_path / "webullsdkcore").mkdir()
    (tmp_path / "webullsdkcore" / "__init__.py").write_text("")
    (tmp_path / "webullsdkcore" / "client.py").write_text("class ApiClient: pass\n")
    (tmp_path / "webullsdkmdata").mkdir()
    (tmp_path / "webullsdkmdata" / "__init__.py").write_text("")
    (tmp_path / "webullsdkmdata" / "api.py").write_text("class MarketDataApi: pass\n")

    class Distribution:
        files = [
            "webullsdkcore/__init__.py", "webullsdkcore/client.py",
            "webullsdkmdata/__init__.py", "webullsdkmdata/api.py",
        ]

        def locate_file(self, file):
            return tmp_path / file

    monkeypatch.setattr("mide.webull_sdk.metadata.distribution", lambda name: Distribution())

    client = create_official_client("key", "secret")

    assert calls[0] == ("ApiClient", {"app_key": "key", "app_secret": "secret"})
    assert calls[1] == ("MarketDataApi", client.api_client)


def test_missing_declared_sdk_fails_once_with_explicit_package(monkeypatch):
    def missing(_name):
        from importlib import metadata
        raise metadata.PackageNotFoundError

    monkeypatch.setattr("mide.webull_sdk.metadata.distribution", missing)
    with pytest.raises(RuntimeError) as error:
        create_official_client("key", "secret")

    assert str(error.value) == (
        "Required Webull SDK package is not installed: webull-openapi-python-sdk"
    )


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


def test_streaming_is_bypassed_until_snapshots_are_proven():
    class ForbiddenStream:
        def __init__(self, *args, **kwargs):
            raise AssertionError("stream must not initialize")
    provider = LiveWebullProvider("key", "secret", rest_client=Rest(),
        universe_client=Universe(), bootstrap=Bootstrap(), stream_class=ForbiddenStream)
    assert provider.initialize_quotes(["HYFM"]) == {"HYFM": 10.0}
    assert provider.diagnostics["webull_stream"]["stream_connection_status"] == "bypassed"


def test_explicit_official_stream_failure_keeps_snapshot_only_universe():
    class BrokenStream:
        def __init__(self, *args, **kwargs):
            raise FileNotFoundError("official stream unavailable")
    provider = LiveWebullProvider("key", "secret", rest_client=Rest(),
        universe_client=Universe(), bootstrap=Bootstrap(), stream_class=BrokenStream,
        enable_streaming=True)
    assert provider.initialize_quotes(["HYFM"]) == {"HYFM": 10.0}
    diagnostic = provider.diagnostics["webull_stream"]
    assert diagnostic["stream_connection_status"] == "error"
    assert diagnostic["snapshot_rest_succeeded"] is True
    assert diagnostic["cached_snapshot_symbols"] == 1


def test_cached_snapshot_load_is_proven_in_diagnostics(caplog):
    provider = LiveWebullProvider("key", "secret", rest_client=Rest(),
        universe_client=Universe())
    provider.initialize_quotes(["AAA", "BBB"])
    with caplog.at_level("INFO"):
        snapshots = provider.snapshots(["AAA", "BBB"])
    diagnostic = provider.diagnostics["webull_stream"]
    assert set(snapshots) == {"AAA", "BBB"}
    assert diagnostic["discovered_symbols"] == 2
    assert diagnostic["cached_snapshot_symbols"] == 2
    assert diagnostic["cached_snapshot_loaded"] is True
    assert "loaded_symbols=2" in caplog.text


def test_obsolete_streaming_token_endpoint_is_absent():
    live_source = inspect.getsource(__import__("mide.webull_live", fromlist=["x"]))
    sdk_source = inspect.getsource(__import__("mide.webull_sdk", fromlist=["x"]))
    obsolete_path = "/api/market-data/streaming/" + "token"
    assert obsolete_path not in live_source
    assert obsolete_path not in sdk_source


def test_http_trace_logs_request_and_response_without_secrets(caplog):
    class Response:
        status_code = 404
        headers = {"content-type": "application/json"}
        text = '{"error":"not found"}'
    class Transport:
        def request(self, method, url, **kwargs): return Response()
    with caplog.at_level("INFO"):
        TracedHTTPTransport(Transport()).request("POST", "https://api.webull.com/missing",
            headers={"x-signature": "secret", "accept": "application/json"}, json={})
    output = caplog.text
    assert "method=POST" in output and "url=https://api.webull.com/missing" in output
    assert "status=404" in output and '{"error":"not found"}' in output
    assert "secret" not in output and "<redacted>" in output


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

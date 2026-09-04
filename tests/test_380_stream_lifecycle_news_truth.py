from threading import Event

import pytest

from mide import gs379_webull_stream_data_truth as stream_truth
from mide.webull_live import LiveWebullProvider


class _NeverConnectClient:
    def __init__(self):
        self.on_connect_success = None
        self.on_quotes_message = None
        self.on_subscribe_success = None
        self.stop = Event()
        self.disconnected = False

    def connect_and_loop_forever(self, logger_enable=True):
        assert logger_enable is False
        self.stop.wait(1)

    def disconnect(self):
        self.disconnected = True
        self.stop.set()


def test_connect_timeout_disconnects_sdk_and_leaves_no_orphan_thread(monkeypatch):
    monkeypatch.setattr(stream_truth, "CONNECT_TIMEOUT_SECONDS", 0.01)
    client = _NeverConnectClient()
    transport = stream_truth.OfficialWebullTickTransport(client, lambda event: None)

    with pytest.raises(TimeoutError, match="did not connect"):
        transport.connect()

    assert client.disconnected is True
    assert transport._closed is True
    assert transport._thread is not None
    assert transport._thread.is_alive() is False


class _NoSubscribeAckClient:
    def __init__(self):
        self.disconnected = False
        self.calls = []

    def subscribe(self, symbols, category, sub_types):
        self.calls.append((list(symbols), category, list(sub_types)))

    def disconnect(self):
        self.disconnected = True


def test_subscribe_timeout_disconnects_connected_transport(monkeypatch):
    monkeypatch.setattr(stream_truth, "SUBSCRIBE_TIMEOUT_SECONDS", 0.01)
    client = _NoSubscribeAckClient()
    transport = stream_truth.OfficialWebullTickTransport(client, lambda event: None)

    with pytest.raises(RuntimeError, match="subscription did not confirm"):
        transport.subscribe(["OLOX"])

    assert client.calls == [(["OLOX"], "US_STOCK", ["TICK"])]
    assert client.disconnected is True
    assert transport._closed is True


class _Subscription:
    def __init__(self):
        self.closed = 0

    def close(self):
        self.closed += 1


class _Provider:
    def __init__(self):
        self._subscription = _Subscription()
        self._subscribed = {"OLOX", "GRI"}
        self.diagnostics = {
            "webull_stream": {
                "stream_connection_status": "connected",
                "stream_replaced_count": 0,
                "stream_cleanup_failures": 0,
            }
        }


def test_new_production_session_retires_prior_process_local_stream():
    stream_truth._reset_active_provider_registry()
    first = _Provider()
    second = _Provider()

    stream_truth._register_active_provider(first)
    stream_truth._register_active_provider(second)

    assert first._subscription is None
    assert first._subscribed == set()
    assert first.diagnostics["webull_stream"]["stream_connection_status"] == "replaced"
    assert first.diagnostics["webull_stream"]["stream_replaced_count"] == 1
    assert second._subscription.closed == 0
    stream_truth._reset_active_provider_registry()


def test_pipeline_news_provenance_uses_completed_scan_runtime_provider():
    provider = object.__new__(LiveWebullProvider)
    provider._walter_native_universe_active = True
    provider._extended_hours_enabled = False
    provider.diagnostics = {
        "news_coverage": {
            "active_provider": "Financial Modeling Prep news",
            "provider_endpoints": ["news/stock", "news/press-releases"],
            "requests_made": 2,
            "articles_received": 70,
            "provider_failures": 0,
        }
    }

    rows = provider.pipeline_sources()
    news = next(row for row in rows if str(row.get("Stage", "")).lower().startswith("news"))

    assert news["Actual provider"] == "Financial Modeling Prep news"
    assert "news/stock" in news["Endpoint / operation"]
    assert "news/press-releases" in news["Endpoint / operation"]
    assert news["Alpaca used"] == "No"


def test_pipeline_news_provenance_never_claims_none_when_runtime_provider_is_known():
    rows = stream_truth._runtime_news_pipeline_rows(
        type("P", (), {"diagnostics": {"news_coverage": {
            "active_provider": "Financial Modeling Prep news"
        }}})(),
        [{
            "Stage": "News",
            "Actual provider": "None (provider abstraction)",
            "Endpoint / operation": "No raw Webull article feed in current pipeline",
            "Code path": "NewsService → provider abstraction",
            "Alpaca used": "No",
        }],
    )

    assert rows[0]["Actual provider"] == "Financial Modeling Prep news"
    assert "None" not in rows[0]["Actual provider"]


def test_gs380_runtime_news_truth_wrapper_is_installed():
    assert getattr(LiveWebullProvider.pipeline_sources, "_gs380_runtime_news_truth", False)

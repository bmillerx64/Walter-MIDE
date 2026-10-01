import builtins
import json
from pathlib import Path

from mide import gs620_live_news_stream as gs620
from mide import gs624_realtime_news_transport as gs624
from mide.authorities import presentation_audio


class FakeThread:
    def __init__(self, *, target=None, args=(), name=None, daemon=None):
        self.target = target
        self.args = args
        self.name = name
        self.daemon = daemon
        self.started = False

    def start(self):
        self.started = True

    def is_alive(self):
        return self.started


class FakeRestNewsClient:
    def news(self, *args, **kwargs):
        return []


def reset_gs620():
    with gs620._LOCK:
        gs620._CACHE.clear()
        gs620._RUNTIME.clear()
        gs620._RUNTIME.update({
            "status": "cold",
            "last_started_at": None,
            "last_completed_at": None,
            "last_error_type": None,
            "articles_received": 0,
        })
        gs620._JOB = None


def test_gs626_dedicated_credentials_start_stream_without_webull_alpaca_client(monkeypatch):
    gs624._reset_for_tests()
    assert gs624.configure_news_credentials("news-key", "news-secret") is True

    captured = {}
    class CaptureThread(FakeThread):
        def start(self):
            captured["args"] = self.args
            super().start()

    monkeypatch.setattr(gs624.threading, "Thread", CaptureThread)

    class WebullOnly:
        provider_name = "Webull OpenAPI"
        _universe_client = None

    trace = gs624.ensure_realtime_news_stream(WebullOnly())

    assert captured["args"] == ("news-key", "news-secret")
    assert trace["status"] == "starting"
    assert trace["auth_status"] == "pending"
    assert trace["credential_source"] == "dedicated news credentials"
    serialized = json.dumps(trace)
    assert "news-key" not in serialized
    assert "news-secret" not in serialized


def test_gs626_gs620_uses_dedicated_rest_client_when_webull_retains_none(monkeypatch):
    reset_gs620()
    fake = FakeRestNewsClient()
    monkeypatch.setattr(gs624, "rest_news_client", lambda: fake)
    monkeypatch.setattr(gs620.threading, "Thread", FakeThread)

    class WebullOnly:
        _universe_client = None

    runtime = gs620.schedule_live_news_poll(WebullOnly())

    assert runtime["status"] == "polling"
    assert gs620._JOB is not None
    assert gs620._JOB.args == (fake,)
    assert gs620._JOB.started is True


def test_gs626_rest_news_client_is_separate_from_webull_provider_state():
    gs624._reset_for_tests()
    assert gs624.configure_news_credentials("dedicated-key", "dedicated-secret")

    client = gs624.rest_news_client()

    assert callable(client.news)
    assert client.headers["APCA-API-KEY-ID"] == "dedicated-key"
    assert client.headers["APCA-API-SECRET-KEY"] == "dedicated-secret"
    trace = gs624.snapshot()
    assert "dedicated-key" not in json.dumps(trace)
    assert "dedicated-secret" not in json.dumps(trace)


def test_gs626_caption_exposes_socket_truth_even_if_rest_cache_unavailable():
    report = {
        "providers": {
            "alpaca_live": {
                "transport_disposition": "UNAVAILABLE",
                "articles_received": 0,
                "realtime_transport": {
                    "status": "streaming",
                    "subscription_status": "marketwide_subscribed",
                    "last_error_category": None,
                },
            },
            "benzinga": {
                "transport_disposition": "UNAVAILABLE",
                "articles_received": 0,
            },
            "fmp": {
                "transport_disposition": "SUCCESS",
                "articles_received": 10,
                "priority_source_counts": {
                    "Reuters": 0,
                    "TipRanks": 0,
                    "Benzinga": 0,
                },
            },
        },
    }

    caption = presentation_audio.catalyst_brief_provider_caption(report)

    assert (
        "Live cache: unavailable / stream streaming / marketwide_subscribed"
        in caption
    )


def test_gs626_app_configures_news_credentials_without_undoing_gs258_boundary():
    app = Path("app.py").read_text(encoding="utf-8")
    gs258 = Path("mide/gs258_cutover.py").read_text(encoding="utf-8")

    configure = app.index(".configure_news_credentials(alpaca_key, alpaca_secret)")
    claim = app.index("claim_process_live_provider(", configure)
    assert configure < claim

    assert 'kwargs["universe_client"] = None' in gs258
    assert "self._universe_client = None" in gs258
    assert 'self.diagnostics["alpaca_runtime_enabled"] = False' in gs258


def test_gs626_news_boundary_has_no_trading_authority():
    source = Path("mide/gs624_realtime_news_transport.py").read_text(encoding="utf-8")
    forbidden = (
        "qualified_for_entry =",
        "qualified_for_alert =",
        "participation_score =",
        "expansion_score =",
        "place_order(",
        "submit_order(",
        "execute_order(",
        "request_scan(",
    )
    assert not any(token in source for token in forbidden)

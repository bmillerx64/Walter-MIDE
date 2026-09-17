from __future__ import annotations

from pathlib import Path

from mide import gs427_flight_recorder_latency_hard_bind as gs427
from mide import gs486_top_level_transport_truth as gs486


class Provider:
    def __init__(self):
        self._subscription = None
        self._subscribed = set()
        self.diagnostics = {
            "news_coverage": {
                "active_provider": "Financial Modeling Prep news",
                "provider_endpoints": ["news/stock"],
                "requests_made": 1,
                "articles_received": 0,
                "requested_symbols": ["PAAI"],
                "symbols_without_articles": ["PAAI"],
                "provider_failures": 0,
            },
            "webull_stream": {
                "stream_connection_status": "error",
                "subscription_failures": ["RuntimeError: socket closed"],
                "disconnect_count": 1,
            },
        }


def test_top_level_transport_survives_inner_story_overwrite(monkeypatch):
    provider = Provider()
    saved = {}

    def inner(_recorder, scan, _records, *args, **kwargs):
        final = dict(scan)
        # Simulate retained GS481/GS480 replacing their own story field.
        final["news_story_trace"] = {"legacy": True}
        saved.update(final)
        return "ok"

    active_globals = {"persist_replayable_scan": inner}
    monkeypatch.setattr(gs427, "_active_recorder_globals", lambda: active_globals)
    monkeypatch.setattr(gs427, "_active_provider", lambda: (provider, "test_provider"))

    assert gs486.install() is True
    result = active_globals["persist_replayable_scan"](None, {"scan": 1}, [])

    assert result == "ok"
    assert saved["news_story_trace"] == {"legacy": True}
    assert saved["news_transport_trace"]["transport_disposition"] == "SUCCESS_EMPTY"
    assert saved["news_transport_trace"]["requested_symbols"] == ["PAAI"]
    assert saved["news_transport_trace"]["top_level_hard_bind"] is True
    assert saved["stream_transport_trace"]["connection_status"] == "error"
    assert saved["stream_transport_trace"]["subscription_failure_count"] == 1
    assert saved["stream_transport_trace"]["subscription_failures_tail"] == ["RuntimeError: socket closed"]
    assert saved["transport_runtime_hard_bind"]["gs486_top_level_transport_truth"] is True


def test_install_is_idempotent(monkeypatch):
    def inner(*args, **kwargs):
        return None

    active_globals = {"persist_replayable_scan": inner}
    monkeypatch.setattr(gs427, "_active_recorder_globals", lambda: active_globals)
    monkeypatch.setattr(gs427, "_active_provider", lambda: (Provider(), "test"))

    assert gs486.install() is True
    first = active_globals["persist_replayable_scan"]
    assert gs486.install() is False
    assert active_globals["persist_replayable_scan"] is first


def test_scope_lock_contains_no_network_or_trading_authority():
    source = Path("mide/gs486_top_level_transport_truth.py").read_text()
    forbidden = (
        ".fetch(", "requests.get", "requests.post", "ensure_stream(", ".subscribe(",
        "qualification", "readiness", "execute", "place_order", "submit_order",
    )
    for token in forbidden:
        assert token not in source
    assert "extra_provider_calls\"] = 0" in source
    assert "network_repair_attempted_here\"] = False" in source


def test_app_and_startup_install_after_gs485():
    app = Path("app.py").read_text()
    assert app.index("_install_gs485_retained_news_transport()") < app.index("_install_gs486_top_level_transport_truth()")

    startup = Path("mide/startup.py").read_text()
    body = startup.split("def ensure_late_runtime_installers() -> None:", 1)[1]
    assert body.index("install_gs485()") < body.index("install_gs486()") < body.index("install_gs483()")

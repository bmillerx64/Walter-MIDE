from __future__ import annotations

import ast
from pathlib import Path

from mide import flight_recorder
from mide import gs427_flight_recorder_latency_hard_bind as gs427
from mide import gs487_cached_recorder_instance_bind as gs487


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


def retained_recorder(saved: dict):
    def persist(_recorder, scan, _records, *args, **kwargs):
        saved.update(scan)
        return scan

    namespace = {
        "__name__": "mide.flight_recorder",
        "persist_replayable_scan": persist,
    }
    exec(
        "def record_scan(self, *, scan, records):\n"
        "    return persist_replayable_scan(self, scan, records)\n",
        namespace,
    )

    class RetainedRecorder:
        pass

    RetainedRecorder.record_scan = namespace["record_scan"]
    return RetainedRecorder(), namespace


def test_exact_cached_recorder_generation_gets_transport_truth(monkeypatch):
    saved = {}
    recorder, retained_globals = retained_recorder(saved)
    provider = Provider()
    retained_original = retained_globals["persist_replayable_scan"]
    current_public_persist = flight_recorder.persist_replayable_scan
    monkeypatch.setattr(gs427, "_active_provider", lambda: (provider, "retained_test_provider"))

    assert gs487.install_for_recorder(recorder) is True
    assert retained_globals["persist_replayable_scan"] is not retained_original
    assert flight_recorder.persist_replayable_scan is current_public_persist

    recorder.record_scan(scan={"scan_id": "retained"}, records=[])

    assert saved["news_transport_trace"]["transport_disposition"] == "SUCCESS_EMPTY"
    assert saved["news_transport_trace"]["requested_symbols"] == ["PAAI"]
    assert saved["news_transport_trace"]["cached_recorder_instance_bind"] is True
    assert saved["stream_transport_trace"]["connection_status"] == "error"
    assert saved["stream_transport_trace"]["subscription_failure_count"] == 1
    assert saved["stream_transport_trace"]["subscription_failures_tail"] == [
        "RuntimeError: socket closed"
    ]
    assert saved["recorder_instance_transport_bind"]["gs487_cached_recorder_instance_bind"] is True
    assert saved["recorder_instance_transport_bind"]["binding"] == gs487.BINDING


def test_cached_recorder_install_is_idempotent(monkeypatch):
    recorder, retained_globals = retained_recorder({})
    monkeypatch.setattr(gs427, "_active_provider", lambda: (Provider(), "test"))

    assert gs487.install_for_recorder(recorder) is True
    first = retained_globals["persist_replayable_scan"]
    assert gs487.install_for_recorder(recorder) is False
    assert retained_globals["persist_replayable_scan"] is first


def test_unknown_recorder_shape_is_nonfatal():
    class NoRecorderMethod:
        pass

    assert gs487.install_for_recorder(NoRecorderMethod()) is False


def test_app_binds_exact_recorder_before_every_record_scan_call():
    source = Path("app.py").read_text()
    function = source.split("def record_scan_safely(", 1)[1].split("\ndef ", 1)[0]
    assert "gs487_cached_recorder_instance_bind" in function
    assert function.index("install_for_recorder(recorder)") < function.index(
        "result = recorder.record_scan("
    )


def test_scope_lock_has_no_network_or_order_calls():
    source = Path("mide/gs487_cached_recorder_instance_bind.py").read_text()
    tree = ast.parse(source)
    forbidden_calls = {
        "subscribe", "ensure_stream", "initialize_quotes",
        "place_order", "submit_order", "execute_order",
    }
    seen = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Attribute):
            seen.add(func.attr)
        elif isinstance(func, ast.Name):
            seen.add(func.id)
    assert not (seen & forbidden_calls)
    assert "import requests" not in source
    assert "import httpx" not in source
    assert 'truth["extra_provider_calls"] = 0' in source
    assert 'truth["network_repair_attempted_here"] = False' in source

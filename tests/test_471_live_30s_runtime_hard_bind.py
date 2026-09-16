from __future__ import annotations

from threading import Lock

from mide import flight_recorder
from mide import gs379_webull_stream_data_truth as gs379
from mide import gs470_30s_activation_truth as gs470
from mide import webull_live, webull_sdk
from mide.market_data import EventType, MarketEvent


class _DataClient:
    def __init__(self):
        self._walter_streaming_client_factory = lambda: object()


def _production_graph_provider(provider_class=None):
    snapshot = object.__new__(webull_live.WebullOpenAPIClient)
    sdk = object.__new__(webull_sdk.WebullSDKClient)
    sdk.sdk_client = _DataClient()
    snapshot.sdk = sdk

    if provider_class is None:
        provider_class = type(
            "RetainedLiveProvider",
            (),
            {"_on_event": lambda self, event: None},
        )
    provider = object.__new__(provider_class)
    provider._snapshot_client = snapshot
    provider._stream_class = None
    provider._bootstrap = None
    provider._enable_streaming = False
    provider._subscription = None
    provider._subscribed = set()
    provider._lock = Lock()
    provider.cache = {}
    provider.diagnostics = {
        "webull_stream": {
            "stream_connection_status": "bypassed",
            "stream_bypass_reason": "streaming disabled",
        }
    }
    provider.warnings = []
    return provider


def test_retained_provider_class_gets_real_gs379_trade_aggregation(monkeypatch):
    provider = _production_graph_provider()
    monkeypatch.setattr(gs379, "_ACTIVE_PROVIDER_REF", None)

    result = gs470.activate_production_30s(provider)

    assert result["runtime_hard_bind"] is True
    assert result["retained_provider_event_hook_patched"] is True
    assert provider._enable_streaming is True
    assert getattr(type(provider)._on_event, "_gs379_tick_aggregation", False) is True
    assert callable(type(provider).stream_30s_bars)

    first = MarketEvent(
        "Webull OpenAPI", EventType.TRADE, "GSUN", 30_000,
        {"price": 0.20, "volume": 100.0},
    )
    second = MarketEvent(
        "Webull OpenAPI", EventType.TRADE, "GSUN", 60_000,
        {"price": 0.22, "volume": 200.0},
    )
    type(provider)._on_event(provider, first)
    type(provider)._on_event(provider, second)

    rows = type(provider).stream_30s_bars(provider, "GSUN")
    assert len(rows) == 1
    assert rows[0]["o"] == 0.20
    assert rows[0]["c"] == 0.20
    assert provider.diagnostics["webull_stream"]["tick_messages_received"] == 2
    assert provider.diagnostics["webull_stream"]["thirty_second_bars_closed"] == 1


def test_retained_scan_context_class_activates_provider_on_late_assignment(monkeypatch):
    calls = []
    monkeypatch.setattr(gs470, "_safe_activate", lambda provider: calls.append(provider) or {})

    class RetainedContext:
        def __init__(self):
            self.provider_instance = None

    context = RetainedContext()
    gs470._bind_context_class(context)
    provider = object()
    context.provider_instance = provider

    assert calls == [provider]
    assert getattr(type(context).__setattr__, gs470._CONTEXT_SETATTR_OWNER, False) is True


def test_scan_context_wrapper_activates_already_retained_provider(monkeypatch):
    from mide import completed_scan

    provider = object()

    class RetainedContext:
        provider_instance = provider

    context = RetainedContext()
    calls = []
    monkeypatch.setattr(gs470, "_safe_activate", lambda value: calls.append(value) or {})

    def base(_state):
        return context

    monkeypatch.setattr(completed_scan, "scan_context", base)
    gs470._install_scan_context_hard_bind()

    returned = completed_scan.scan_context({})
    assert returned is context
    assert calls == [provider]


def test_hard_recorder_health_binds_exact_active_globals(monkeypatch):
    captured = {}

    def base(_recorder, scan, _records, *args, **kwargs):
        captured.update(scan)
        return scan

    active_globals = {"persist_replayable_scan": base}
    monkeypatch.setattr(gs470, "_active_recorder_globals", lambda: active_globals)
    monkeypatch.setattr(
        gs470,
        "stream_30s_health",
        lambda _provider: {"runtime_hard_bind": True, "tick_messages_received": 7},
    )
    monkeypatch.setattr(gs470, "_active_or_last_provider", lambda: object())

    gs470._install_hard_recorder_health()
    active_globals["persist_replayable_scan"](
        object(), {"scan_id": "current-runtime"}, []
    )

    assert captured["stream_30s_health"] == {
        "runtime_hard_bind": True,
        "tick_messages_received": 7,
    }
    assert getattr(
        active_globals["persist_replayable_scan"], gs470._HARD_RECORDER_OWNER, False
    ) is True


def test_existing_subscription_is_retired_when_retained_hook_is_repaired(monkeypatch):
    provider = _production_graph_provider()
    provider._subscription = object()
    provider._subscribed = {"DLXY", "QCLS"}
    monkeypatch.setattr(gs379, "_ACTIVE_PROVIDER_REF", None)
    retired = []

    def retire(value):
        retired.append(value)
        value._subscription = None
        value._subscribed.clear()

    monkeypatch.setattr(gs379, "_retire_provider_stream", retire)

    result = gs470.activate_production_30s(provider)

    assert retired == [provider]
    assert result["subscription_retired_for_rebind"] is True
    assert "callback must be rebound" in result["subscription_retirement_reason"]
    assert provider._subscription is None


def test_nonproduction_provider_is_not_force_enabled_or_class_patched(monkeypatch):
    class InjectedProvider:
        def _on_event(self, event):
            return None

    provider = object.__new__(InjectedProvider)
    provider._snapshot_client = object()
    provider._stream_class = object()
    provider._bootstrap = object()
    provider._enable_streaming = False
    provider._subscription = None
    provider._subscribed = set()
    provider._lock = Lock()
    provider.diagnostics = {"webull_stream": {}}
    monkeypatch.setattr(gs379, "_ACTIVE_PROVIDER_REF", None)

    result = gs470.activate_production_30s(provider)

    assert result["production_sdk_graph"] is False
    assert provider._enable_streaming is False
    assert not getattr(InjectedProvider._on_event, "_gs379_tick_aggregation", False)
    assert gs379._ACTIVE_PROVIDER_REF is None


def test_gs471_scope_lock_remains_market_data_lifecycle_only():
    from pathlib import Path

    source = Path("mide/gs470_30s_activation_truth.py").read_text(encoding="utf-8")
    forbidden = (
        "qualified_for_watch =",
        "qualified_for_entry =",
        "qualified_for_alert =",
        "candidate_status =",
        "participation_score =",
        "expansion_score =",
        "vwap_distance_pct =",
        "place_order(",
        "submit_order(",
        "play_alert(",
        ".bars(",
        ".history(",
    )
    assert not any(token in source for token in forbidden)
    assert '_install_hard_recorder_health()' in source
    assert '_install_scan_context_hard_bind()' in source
    assert '"synthetic_30s_bars": False' in source
    assert '"genuine_webull_tick_only": True' in source

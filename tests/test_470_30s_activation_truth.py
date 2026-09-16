from __future__ import annotations

from collections import deque
from pathlib import Path
from threading import Lock

from mide import flight_recorder
from mide import gs379_webull_stream_data_truth as gs379
from mide import gs470_30s_activation_truth as gs470
from mide import webull_live, webull_sdk


class _DataClient:
    def __init__(self):
        self._walter_streaming_client_factory = lambda: object()


def _production_provider(*, enabled=False):
    snapshot = object.__new__(webull_live.WebullOpenAPIClient)
    sdk = object.__new__(webull_sdk.WebullSDKClient)
    sdk.sdk_client = _DataClient()
    snapshot.sdk = sdk

    provider = object.__new__(webull_live.LiveWebullProvider)
    provider._snapshot_client = snapshot
    provider._stream_class = None
    provider._bootstrap = None
    provider._enable_streaming = enabled
    provider._subscription = None
    provider._subscribed = set()
    provider._lock = Lock()
    provider.diagnostics = {
        "webull_stream": {
            "stream_connection_status": "bypassed" if not enabled else "disconnected",
            "stream_bypass_reason": "streaming disabled" if not enabled else None,
        }
    }
    provider.warnings = []
    return provider


def test_disabled_real_production_provider_is_reactivated_and_registered(monkeypatch):
    provider = _production_provider(enabled=False)
    monkeypatch.setattr(gs379, "_ACTIVE_PROVIDER_REF", None)

    result = gs470.activate_production_30s(provider)

    assert result["production_sdk_graph"] is True
    assert result["streaming_enabled_before"] is False
    assert result["streaming_enabled_now"] is True
    assert result["activation_performed"] is True
    assert provider._enable_streaming is True
    assert isinstance(provider._gs379_30s_current, dict)
    assert isinstance(provider._gs379_30s_closed, dict)
    assert gs379._ACTIVE_PROVIDER_REF() is provider
    assert provider.diagnostics["webull_stream"]["stream_connection_status"] == "disconnected"
    assert provider.diagnostics["webull_stream"]["stream_bypass_reason"] is None


def test_reactivation_preserves_existing_30s_state_and_counters(monkeypatch):
    provider = _production_provider(enabled=False)
    provider._gs379_30s_current = {"DLXY": {"t": 123}}
    provider._gs379_30s_closed = {"DLXY": deque([{"t": 100}], maxlen=240)}
    provider.diagnostics["webull_stream"]["tick_messages_received"] = 91
    provider.diagnostics["webull_stream"]["thirty_second_bars_closed"] = 44
    monkeypatch.setattr(gs379, "_ACTIVE_PROVIDER_REF", None)

    gs470.activate_production_30s(provider)

    assert provider._gs379_30s_current == {"DLXY": {"t": 123}}
    assert list(provider._gs379_30s_closed["DLXY"]) == [{"t": 100}]
    assert provider.diagnostics["webull_stream"]["tick_messages_received"] == 91
    assert provider.diagnostics["webull_stream"]["thirty_second_bars_closed"] == 44


def test_injected_nonproduction_provider_is_never_force_enabled(monkeypatch):
    provider = _production_provider(enabled=False)
    provider._snapshot_client = object()
    monkeypatch.setattr(gs379, "_ACTIVE_PROVIDER_REF", None)

    result = gs470.activate_production_30s(provider)

    assert result["production_sdk_graph"] is False
    assert result["activation_performed"] is False
    assert provider._enable_streaming is False
    assert gs379._ACTIVE_PROVIDER_REF is None


def test_initialize_quotes_wrapper_activates_before_base_can_bypass(monkeypatch):
    provider = _production_provider(enabled=False)
    monkeypatch.setattr(gs379, "_ACTIVE_PROVIDER_REF", None)
    calls = []

    def base(self, symbols, *args, **kwargs):
        calls.append((list(symbols), self._enable_streaming))
        return {"DLXY": 0.95}

    monkeypatch.setattr(webull_live.LiveWebullProvider, "initialize_quotes", base)
    gs470._install_activation_boundary()

    result = webull_live.LiveWebullProvider.initialize_quotes(provider, ["DLXY"])

    assert result == {"DLXY": 0.95}
    assert calls == [(["DLXY"], True)]


def test_stream_health_proves_disabled_disconnected_or_live_states(monkeypatch):
    provider = _production_provider(enabled=False)
    monkeypatch.setattr(gs379, "_ACTIVE_PROVIDER_REF", None)
    disabled = gs470.stream_30s_health(provider)
    assert disabled["production_sdk_graph"] is True
    assert disabled["streaming_enabled"] is False
    assert disabled["subscription_present"] is False
    assert disabled["stream_factory_present"] is True

    gs470.activate_production_30s(provider)
    provider._subscription = object()
    provider._subscribed = {"DLXY", "QCLS"}
    provider.diagnostics["webull_stream"].update(
        stream_connection_status="connected",
        tick_messages_received=17,
        last_tick_timestamp_ms=None,
        thirty_second_bars_closed=8,
        thirty_second_symbols_ready=1,
    )
    live = gs470.stream_30s_health(provider)
    assert live["streaming_enabled"] is True
    assert live["subscription_present"] is True
    assert live["subscribed_symbol_count"] == 2
    assert live["connection_status"] == "connected"
    assert live["tick_messages_received"] == 17
    assert live["thirty_second_bars_closed"] == 8
    assert live["thirty_second_symbols_ready"] == 1
    assert live["synthetic_30s_bars"] is False


def test_recorder_persists_stream_health_even_when_no_30s_bars(monkeypatch):
    provider = _production_provider(enabled=False)
    monkeypatch.setattr(gs379, "_ACTIVE_PROVIDER_REF", None)
    gs470.activate_production_30s(provider)
    captured = {}

    def base(recorder, scan, records, *args, **kwargs):
        captured.update(scan)
        return scan

    monkeypatch.setattr(flight_recorder, "persist_replayable_scan", base)
    gs470._install_recorder_health()

    flight_recorder.persist_replayable_scan(object(), {"scan_id": "scan"}, [])

    health = captured["stream_30s_health"]
    assert health["provider_present"] is True
    assert health["production_sdk_graph"] is True
    assert health["streaming_enabled"] is True
    assert health["tick_messages_received"] == 0
    assert health["thirty_second_bars_closed"] == 0


def test_install_is_idempotent(monkeypatch):
    def base(self, symbols):
        return True

    monkeypatch.setattr(webull_live.LiveWebullProvider, "initialize_quotes", base)
    gs470._install_activation_boundary()
    once = webull_live.LiveWebullProvider.initialize_quotes
    gs470._install_activation_boundary()
    twice = webull_live.LiveWebullProvider.initialize_quotes

    assert once is twice
    assert getattr(once, gs470._INIT_OWNER, False) is True


def test_gs384_installs_gs470_outside_gs469_before_idempotence_return():
    source = Path("mide/gs384_diagnostic_signal_to_noise.py").read_text(encoding="utf-8")
    assert "gs470_30s_activation_truth" in source
    assert source.index("install_gs469()") < source.index("install_gs470()")
    assert source.index("install_gs470()") < source.index(
        'if getattr(current_sources, "_gs384_signal_to_noise", False):'
    )


def test_scope_lock_no_synthetic_or_trading_authority_changes():
    source = Path("mide/gs470_30s_activation_truth.py").read_text(encoding="utf-8")
    forbidden = (
        "provider.bars(",
        "client.bars(",
        "qualified_for_watch =",
        "qualified_for_entry =",
        "qualified_for_alert =",
        "candidate_status =",
        "participation_score =",
        "expansion_score =",
        "vwap_value =",
        "place_order(",
        "play_alert(",
    )
    assert not any(token in source for token in forbidden)
    assert '"synthetic_30s_bars": False' in source
    assert '"genuine_webull_tick_only": True' in source

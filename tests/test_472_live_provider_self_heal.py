from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from mide import gs425_latency_truth_recorder as gs425
from mide import gs427_flight_recorder_latency_hard_bind as gs427
from mide import gs470_30s_activation_truth as gs470


class _Provider:
    def __init__(self):
        self.diagnostics = {"webull_stream": {}}


def test_active_provider_self_heals_exact_stage6_provider(monkeypatch):
    provider = _Provider()
    calls = []
    monkeypatch.setattr(gs425, "_provider_from_trace", lambda: provider)
    monkeypatch.setattr(
        gs470,
        "_safe_activate",
        lambda value: calls.append(value) or {"runtime_hard_bind": True},
    )

    resolved, source = gs427._active_provider()

    assert resolved is provider
    assert source == "gs425_stage6_trace"
    assert calls == [provider]
    self_heal = provider.diagnostics["webull_stream"]["gs472_recorder_provider_self_heal"]
    assert self_heal["performed"] is True
    assert self_heal["network_subscription_started_here"] is False
    assert self_heal["next_initialize_owns_stream_start"] is True


def test_runtime_identity_keeps_30s_health_inside_proven_old_wrapper_contract(monkeypatch):
    provider = _Provider()
    monkeypatch.setattr(gs425, "_provider_from_trace", lambda: provider)
    monkeypatch.setattr(gs470, "_safe_activate", lambda value: {"runtime_hard_bind": True})
    monkeypatch.setattr(
        gs470,
        "stream_30s_health",
        lambda value: {
            "provider_present": value is provider,
            "streaming_enabled": True,
            "tick_messages_received": 7,
            "thirty_second_bars_closed": 3,
            "genuine_webull_tick_only": True,
            "synthetic_30s_bars": False,
        },
    )

    # This deliberately mirrors the pre-GS472 GS427 wrapper body: retained wrapper
    # code performs global lookups for these helpers even when its function object
    # survives a Streamlit hot deploy.
    _provider, source = gs427._active_provider()
    identity = gs427._runtime_identity(source)

    assert identity["gs427_hard_bind"] is True
    assert identity["gs472_provider_self_heal"] is True
    assert identity["provider_source"] == "gs425_stage6_trace"
    assert identity["stream_30s_health"]["provider_present"] is True
    assert identity["stream_30s_health"]["tick_messages_received"] == 7
    assert identity["stream_30s_health"]["thirty_second_bars_closed"] == 3
    assert identity["stream_30s_health"]["gs472_recorder_provider_self_heal"] is True


def test_install_persists_top_level_health_on_exact_active_recorder_binding(monkeypatch):
    provider = _Provider()
    captured = {}

    def base(_recorder, scan, _records, *args, **kwargs):
        captured.update(scan)
        return scan

    globals_dict = {"persist_replayable_scan": base}
    monkeypatch.setattr(gs427, "_active_recorder_globals", lambda: globals_dict)
    monkeypatch.setattr(gs427, "_active_provider", lambda: (provider, "gs425_stage6_trace"))
    monkeypatch.setattr(
        gs427,
        "_runtime_identity",
        lambda source: {"provider_source": source, "gs472_provider_self_heal": True},
    )
    monkeypatch.setattr(
        gs427,
        "_provider_health",
        lambda value: {
            "provider_present": value is provider,
            "tick_messages_received": 11,
            "thirty_second_bars_closed": 5,
        },
    )
    monkeypatch.setattr(
        gs425,
        "build_latency_truth",
        lambda value: {"provider_present": value is provider},
    )

    gs427.install()
    globals_dict["persist_replayable_scan"](object(), {"scan_id": "x"}, [])

    assert captured["recorder_runtime_identity"]["gs472_provider_self_heal"] is True
    assert captured["stream_30s_health"]["provider_present"] is True
    assert captured["stream_30s_health"]["tick_messages_received"] == 11
    assert captured["stream_30s_health"]["thirty_second_bars_closed"] == 5


def test_no_provider_is_safe_and_does_not_claim_self_heal(monkeypatch):
    monkeypatch.setattr(gs425, "_provider_from_trace", lambda: None)
    from mide import gs386_30s_observational_recorder as gs386

    monkeypatch.setattr(gs386, "_active_provider", lambda: None)
    calls = []
    monkeypatch.setattr(gs470, "_safe_activate", lambda value: calls.append(value))

    provider, source = gs427._active_provider()

    assert provider is None
    assert source == "unavailable"
    assert calls == []


def test_scope_lock_recorder_self_heal_never_starts_network_or_changes_trading_authority():
    source = Path("mide/gs427_flight_recorder_latency_hard_bind.py").read_text(encoding="utf-8")
    forbidden = (
        ".ensure_stream(",
        "provider.ensure_stream(",
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
    assert '"network_subscription_started_here": False' in source
    assert '"genuine_webull_tick_only": True' in source

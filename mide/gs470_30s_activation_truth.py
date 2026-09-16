"""GS470: enforce live production 30-second activation and persist its health truth.

The first post-GS469 Flight Recorder validation still showed zero canonical 30-second
snapshots: 19 GS390 validation symbols across 13 current-runtime scans all had
``thirty_second.latest_closed = None``.  GS469 can repair a stale *enabled* stream,
but its continuity wrapper deliberately returns immediately when a retained provider
reports ``_enable_streaming = False``.  A warm Streamlit provider can therefore remain
REST-only forever even though Walter is in real Live Webull mode.

GS470 closes that activation seam at the existing ``initialize_quotes`` boundary.
Before every real production Webull snapshot cycle it:
- recognizes only Walter's SDK-owned ``WebullOpenAPIClient`` provider graph;
- restores the GS379 30s aggregation buffers/counters if a retained provider predates
  the current module generation;
- re-enables streaming when that production provider is unexpectedly disabled;
- reasserts the provider as GS379's active 30s source, after which GS469 owns normal
  heartbeat/reconnect behavior;
- persists a small ``stream_30s_health`` Flight Recorder block on every scan, including
  dead/no-bar scans, so live validation can distinguish disabled, disconnected,
  subscribed-without-TICK, and TICK-without-bars states.

Safety contract:
- genuine Webull OpenAPI TICK remains the only 30s source;
- no synthetic 30s bars and no historical 30s fallback are introduced;
- injected/test providers are never force-enabled;
- discovery, scoring, ranking, participation/expansion, VWAP/ST formulas,
  qualification, readiness, alerts, execution, session authority and orders are
  unchanged.
"""
from __future__ import annotations

from collections import deque
from datetime import datetime, timezone
from functools import wraps
import weakref
from typing import Any


AUTHORITY = "LIVE_WEBULL_PRODUCTION_30S_ACTIVATION"
THIRTY_SECOND_HISTORY = 240
_INIT_OWNER = "_walter_gs470_30s_activation_truth_owner"
_RECORDER_OWNER = "_walter_gs470_30s_health_recorder_owner"
_LAST_PROVIDER_REF = None


def _identity(value: Any) -> tuple[str, str]:
    cls = type(value)
    return str(getattr(cls, "__module__", "")), str(getattr(cls, "__name__", ""))


def _production_sdk_graph(provider) -> bool:
    """Recognize Walter's real SDK-owned Live Webull graph without enabling injections."""
    if provider is None:
        return False
    snapshot_client = getattr(provider, "_snapshot_client", None)
    if _identity(snapshot_client) != ("mide.webull_live", "WebullOpenAPIClient"):
        return False
    sdk = getattr(snapshot_client, "sdk", None)
    if _identity(sdk) != ("mide.webull_sdk", "WebullSDKClient"):
        return False
    if getattr(provider, "_stream_class", None) is not None:
        return False
    if getattr(provider, "_bootstrap", None) is not None:
        return False
    return True


def _stream_diagnostics(provider) -> dict:
    diagnostics = getattr(provider, "diagnostics", None)
    if not isinstance(diagnostics, dict):
        return {}
    stream = diagnostics.get("webull_stream")
    if not isinstance(stream, dict):
        stream = {}
        diagnostics["webull_stream"] = stream
    return stream


def _ensure_gs379_state(provider) -> bool:
    """Hydrate missing GS379 observational state without clearing live retained bars."""
    changed = False
    lock = getattr(provider, "_lock", None)
    if lock is None:
        return False

    with lock:
        if not isinstance(getattr(provider, "_gs379_30s_current", None), dict):
            provider._gs379_30s_current = {}
            changed = True
        if not isinstance(getattr(provider, "_gs379_30s_closed", None), dict):
            provider._gs379_30s_closed = {}
            changed = True

    stream = _stream_diagnostics(provider)
    defaults = {
        "tick_messages_received": 0,
        "tick_symbols_seen": 0,
        "last_tick_timestamp_ms": None,
        "thirty_second_bars_closed": 0,
        "thirty_second_symbols_ready": 0,
        "out_of_order_ticks": 0,
        "unsubscribed_symbols": 0,
        "unsubscribe_failures": 0,
        "stream_replaced_count": 0,
        "stream_cleanup_failures": 0,
        "thirty_second_authority": "OBSERVATIONAL_ONLY",
    }
    for key, default in defaults.items():
        if key not in stream:
            stream[key] = default
            changed = True
    return changed


def _remember_provider(provider) -> None:
    global _LAST_PROVIDER_REF
    try:
        _LAST_PROVIDER_REF = weakref.ref(provider)
    except TypeError:
        _LAST_PROVIDER_REF = None


def _last_provider():
    reference = _LAST_PROVIDER_REF
    if reference is None:
        return None
    try:
        return reference()
    except TypeError:
        return None


def activate_production_30s(provider) -> dict:
    """Make the real Live Webull provider stream-capable before snapshot completion."""
    from . import gs379_webull_stream_data_truth as gs379

    production = _production_sdk_graph(provider)
    stream = _stream_diagnostics(provider)
    enabled_before = bool(getattr(provider, "_enable_streaming", False)) if provider is not None else False
    state_rehydrated = False
    enabled_now = False
    rebound = False

    if production:
        state_rehydrated = _ensure_gs379_state(provider)
        if not getattr(provider, "_enable_streaming", False):
            provider._enable_streaming = True
            enabled_now = True
            if getattr(provider, "_subscription", None) is None:
                stream["stream_connection_status"] = "disconnected"
                stream["stream_bypass_reason"] = None
        active_ref = getattr(gs379, "_ACTIVE_PROVIDER_REF", None)
        active = active_ref() if active_ref is not None else None
        if active is not provider:
            gs379._register_active_provider(provider)
            rebound = True
        _remember_provider(provider)

    stream["gs470_30s_activation_truth"] = {
        "authority": AUTHORITY,
        "production_sdk_graph": production,
        "streaming_enabled_before": enabled_before,
        "streaming_enabled_now": bool(getattr(provider, "_enable_streaming", False)) if provider is not None else False,
        "activation_performed": enabled_now,
        "gs379_state_rehydrated": state_rehydrated,
        "active_provider_reasserted": rebound,
        "genuine_webull_tick_only": True,
        "synthetic_30s_bars": False,
        "entry_authority_changed": False,
    }
    return dict(stream["gs470_30s_activation_truth"])


def _int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _last_tick_age_seconds(last_tick_ms: Any) -> float | None:
    try:
        stamp = int(last_tick_ms)
    except (TypeError, ValueError):
        return None
    if stamp <= 0:
        return None
    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    return round(max(0.0, (now_ms - stamp) / 1000.0), 1)


def _stream_factory_present(provider) -> bool:
    snapshot_client = getattr(provider, "_snapshot_client", None)
    sdk = getattr(snapshot_client, "sdk", None)
    data_client = getattr(sdk, "sdk_client", None)
    return callable(getattr(data_client, "_walter_streaming_client_factory", None))


def stream_30s_health(provider) -> dict:
    """Return bounded non-secret liveness evidence even when zero 30s bars exist."""
    if provider is None:
        return {
            "authority": AUTHORITY,
            "provider_present": False,
            "production_sdk_graph": False,
            "streaming_enabled": False,
            "subscription_present": False,
            "subscribed_symbol_count": 0,
            "connection_status": "provider unavailable",
            "tick_messages_received": 0,
            "last_tick_timestamp_ms": None,
            "last_tick_age_seconds": None,
            "thirty_second_bars_closed": 0,
            "thirty_second_symbols_ready": 0,
            "stream_factory_present": False,
            "genuine_webull_tick_only": True,
            "synthetic_30s_bars": False,
        }

    stream = _stream_diagnostics(provider)
    continuity = dict(stream.get("gs469_30s_stream_continuity") or {})
    activation = dict(stream.get("gs470_30s_activation_truth") or {})
    last_tick = stream.get("last_tick_timestamp_ms")
    return {
        "authority": AUTHORITY,
        "provider_present": True,
        "production_sdk_graph": _production_sdk_graph(provider),
        "streaming_enabled": bool(getattr(provider, "_enable_streaming", False)),
        "subscription_present": getattr(provider, "_subscription", None) is not None,
        "subscribed_symbol_count": len(set(getattr(provider, "_subscribed", set()) or set())),
        "connection_status": str(stream.get("stream_connection_status") or "unknown"),
        "tick_messages_received": _int(stream.get("tick_messages_received")),
        "last_tick_timestamp_ms": _int(last_tick, default=0) or None,
        "last_tick_age_seconds": _last_tick_age_seconds(last_tick),
        "thirty_second_bars_closed": _int(stream.get("thirty_second_bars_closed")),
        "thirty_second_symbols_ready": _int(stream.get("thirty_second_symbols_ready")),
        "stream_factory_present": _stream_factory_present(provider),
        "gs469_restart_count": _int(stream.get("gs469_stale_stream_restarts")),
        "gs469_restart_performed_last_check": bool(continuity.get("restart_performed")),
        "gs469_restart_reason_last_check": continuity.get("restart_reason"),
        "gs470_activation_performed": bool(activation.get("activation_performed")),
        "gs470_state_rehydrated": bool(activation.get("gs379_state_rehydrated")),
        "genuine_webull_tick_only": True,
        "synthetic_30s_bars": False,
        "entry_authority_changed": False,
    }


def _active_or_last_provider():
    from . import gs379_webull_stream_data_truth as gs379

    reference = getattr(gs379, "_ACTIVE_PROVIDER_REF", None)
    if reference is not None:
        try:
            provider = reference()
        except TypeError:
            provider = None
        if provider is not None:
            return provider
    return _last_provider()


def _install_activation_boundary() -> None:
    from . import webull_live

    current = webull_live.LiveWebullProvider.initialize_quotes
    if getattr(current, _INIT_OWNER, False):
        return

    @wraps(current)
    def initialize_quotes(self, symbols, *args, **kwargs):
        activate_production_30s(self)
        return current(self, symbols, *args, **kwargs)

    initialize_quotes._gs470_30s_activation_truth = True
    initialize_quotes._gs470_original = current
    setattr(initialize_quotes, _INIT_OWNER, True)
    webull_live.LiveWebullProvider.initialize_quotes = initialize_quotes


def _install_recorder_health() -> None:
    from . import flight_recorder

    current = flight_recorder.persist_replayable_scan
    if getattr(current, _RECORDER_OWNER, False):
        return

    @wraps(current)
    def persist_replayable_scan(recorder, scan: dict, records, *args, **kwargs):
        enriched = dict(scan or {})
        enriched["stream_30s_health"] = stream_30s_health(_active_or_last_provider())
        return current(recorder, enriched, records, *args, **kwargs)

    persist_replayable_scan._gs470_30s_activation_truth = True
    persist_replayable_scan._gs470_original = current
    setattr(persist_replayable_scan, _RECORDER_OWNER, True)
    flight_recorder.persist_replayable_scan = persist_replayable_scan


def install() -> None:
    """Install activation before quote initialization and always-on recorder health."""
    _install_activation_boundary()
    _install_recorder_health()

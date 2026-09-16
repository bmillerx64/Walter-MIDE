"""GS470/GS471: enforce production 30-second truth across warm Streamlit generations.

Fresh Flight Recorder #73 proved the first GS470 deployment was not actually bound to
Walter's retained live runtime. Build ``a41ab40b0aa1`` produced 19 current-runtime
scans and 47 GS390 validation-symbol observations with zero non-null 30-second
snapshots, and the promised ``stream_30s_health`` block was absent from every scan.
That combination localizes the failure to the same hot-reload ownership seam GS427
previously found in Flight Recorder: installing wrappers on the newest module/class
objects is not enough when Streamlit retains an older ScanContext, provider class, or
recorder function graph.

This module therefore keeps GS470's clean-process wrappers and adds the GS471 hard
bind:
- bind the *actual* provider currently stored in ScanContext, regardless of which
  module generation created it;
- intercept later ``provider_instance`` assignments on that retained context class so
  a newly-created provider is activated before its first ``initialize_quotes`` call;
- rehydrate GS379's observational 30s state without clearing valid live bars;
- if the retained provider class missed GS379's TRADE aggregation hook, attach that
  hook to the provider's actual class;
- if the retained WebullSDKClient class missed GS379's TICK transport hook, attach it
  to the actual SDK class when a stream factory is already present;
- retire an inherited subscription when activation/hook repair makes its captured
  callback obsolete or when it has no/stale TICK heartbeat, so the next ordinary
  initialize cycle creates a fresh genuine Webull TICK subscription;
- hard-bind ``stream_30s_health`` into the exact recorder globals dictionary reached
  by the retained ``FlightRecorder.record_scan`` function graph.

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

from .market_data import EventType, MarketEvent


AUTHORITY = "LIVE_WEBULL_PRODUCTION_30S_ACTIVATION"
THIRTY_SECOND_HISTORY = 240
STALE_TICK_SECONDS = 180.0
_INIT_OWNER = "_walter_gs470_30s_activation_truth_owner"
_RECORDER_OWNER = "_walter_gs470_30s_health_recorder_owner"
_HARD_RECORDER_OWNER = "_walter_gs471_30s_health_hard_bind_owner"
_SCAN_CONTEXT_OWNER = "_walter_gs471_scan_context_30s_owner"
_CONTEXT_SETATTR_OWNER = "_walter_gs471_context_provider_setattr_owner"
_PROVIDER_EVENT_OWNER = "_walter_gs471_retained_provider_event_owner"
_SDK_STREAM_OWNER = "_walter_gs471_retained_sdk_stream_owner"
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
        diagnostics = {}
        try:
            provider.diagnostics = diagnostics
        except Exception:
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


def _patch_retained_provider_event(provider) -> bool:
    """Attach GS379's TRADE aggregation to the actual retained provider class."""
    from . import gs379_webull_stream_data_truth as gs379

    provider_class = type(provider)
    current = getattr(provider_class, "_on_event", None)
    if not callable(current):
        return False
    if getattr(current, "_gs379_tick_aggregation", False) or getattr(
        current, _PROVIDER_EVENT_OWNER, False
    ):
        if not callable(getattr(provider_class, "stream_30s_bars", None)):
            provider_class.stream_30s_bars = gs379._stream_30s_bars
        return False

    @wraps(current)
    def on_event(self, event: MarketEvent) -> None:
        _ensure_gs379_state(self)
        if event.type == EventType.TRADE:
            if event.symbol not in self._gs379_30s_closed:
                with self._lock:
                    self._gs379_30s_closed.setdefault(
                        event.symbol,
                        deque(maxlen=THIRTY_SECOND_HISTORY),
                    )
            if not gs379._record_tick(self, event):
                return
            payload = dict(event.payload)
            payload["trade_size"] = payload.pop("volume", None)
            event = MarketEvent(
                event.provider,
                event.type,
                event.symbol,
                event.source_timestamp_ms,
                payload,
                event.sequence,
                event.wire_bytes,
            )
        current(self, event)

    on_event._gs379_tick_aggregation = True
    on_event._gs471_original = current
    setattr(on_event, _PROVIDER_EVENT_OWNER, True)
    provider_class._on_event = on_event
    provider_class.stream_30s_bars = gs379._stream_30s_bars
    return True


def _patch_retained_sdk_stream(provider) -> bool:
    """Attach GS379's TICK transport to the actual retained SDK adapter class."""
    from . import gs379_webull_stream_data_truth as gs379

    snapshot = getattr(provider, "_snapshot_client", None)
    sdk = getattr(snapshot, "sdk", None)
    data_client = getattr(sdk, "sdk_client", None)
    factory = getattr(data_client, "_walter_streaming_client_factory", None)
    sdk_class = type(sdk) if sdk is not None else None
    current = getattr(sdk_class, "stream", None) if sdk_class is not None else None
    if not callable(current) or not callable(factory):
        return False
    if getattr(current, "_gs379_tick_transport", False) or getattr(
        current, _SDK_STREAM_OWNER, False
    ):
        return False

    @wraps(current)
    def stream(self, callback):
        active_factory = getattr(self.sdk_client, "_walter_streaming_client_factory", None)
        if not callable(active_factory):
            raise RuntimeError("Webull OpenAPI SDK lacks DataStreamingClient")
        return gs379.OfficialWebullTickTransport(active_factory(), callback)

    stream._gs379_tick_transport = True
    stream._gs471_original = current
    setattr(stream, _SDK_STREAM_OWNER, True)
    sdk_class.stream = stream
    return True


def _tick_age_seconds(provider) -> float | None:
    raw = _stream_diagnostics(provider).get("last_tick_timestamp_ms")
    try:
        stamp = int(raw)
    except (TypeError, ValueError):
        return None
    if stamp <= 0:
        return None
    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    return max(0.0, (now_ms - stamp) / 1000.0)


def _retire_obsolete_subscription(provider, *, force: bool = False) -> tuple[bool, str | None]:
    """Retire a captured old callback or dead TICK transport before next initialize."""
    subscription = getattr(provider, "_subscription", None)
    if subscription is None:
        return False, None

    age = _tick_age_seconds(provider)
    reason = None
    if force:
        reason = "runtime 30s hook/activation changed; subscription callback must be rebound"
    elif age is None:
        reason = "subscribed Webull transport has no observed TICK heartbeat"
    elif age > STALE_TICK_SECONDS:
        reason = f"last Webull TICK heartbeat is {age:.1f}s old"
    if reason is None:
        return False, None

    from . import gs379_webull_stream_data_truth as gs379

    gs379._retire_provider_stream(provider)
    return True, reason


def activate_production_30s(provider) -> dict:
    """Hard-bind the actual Live Webull provider before snapshot completion."""
    from . import gs379_webull_stream_data_truth as gs379

    production = _production_sdk_graph(provider)
    stream = _stream_diagnostics(provider)
    enabled_before = bool(getattr(provider, "_enable_streaming", False)) if provider is not None else False
    state_rehydrated = False
    enabled_now = False
    rebound = False
    provider_event_patched = False
    sdk_stream_patched = False
    subscription_retired = False
    retirement_reason = None

    if production:
        state_rehydrated = _ensure_gs379_state(provider)
        provider_event_patched = _patch_retained_provider_event(provider)
        sdk_stream_patched = _patch_retained_sdk_stream(provider)
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
        subscription_retired, retirement_reason = _retire_obsolete_subscription(
            provider,
            force=bool(enabled_now or provider_event_patched or sdk_stream_patched),
        )
        _remember_provider(provider)

    stream["gs470_30s_activation_truth"] = {
        "authority": AUTHORITY,
        "production_sdk_graph": production,
        "streaming_enabled_before": enabled_before,
        "streaming_enabled_now": bool(getattr(provider, "_enable_streaming", False)) if provider is not None else False,
        "activation_performed": enabled_now,
        "gs379_state_rehydrated": state_rehydrated,
        "active_provider_reasserted": rebound,
        "retained_provider_event_hook_patched": provider_event_patched,
        "retained_sdk_stream_hook_patched": sdk_stream_patched,
        "subscription_retired_for_rebind": subscription_retired,
        "subscription_retirement_reason": retirement_reason,
        "runtime_hard_bind": True,
        "genuine_webull_tick_only": True,
        "synthetic_30s_bars": False,
        "entry_authority_changed": False,
    }
    return dict(stream["gs470_30s_activation_truth"])


def _safe_activate(provider) -> dict:
    """Never let observational stream repair break Walter's snapshot scan path."""
    try:
        return activate_production_30s(provider)
    except Exception as exc:
        stream = _stream_diagnostics(provider)
        stream["gs471_runtime_hard_bind_error"] = type(exc).__name__
        return {
            "authority": AUTHORITY,
            "production_sdk_graph": _production_sdk_graph(provider),
            "runtime_hard_bind": True,
            "activation_error": type(exc).__name__,
            "genuine_webull_tick_only": True,
            "synthetic_30s_bars": False,
            "entry_authority_changed": False,
        }


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
            "runtime_hard_bind": True,
            "genuine_webull_tick_only": True,
            "synthetic_30s_bars": False,
        }

    stream = _stream_diagnostics(provider)
    continuity = dict(stream.get("gs469_30s_stream_continuity") or {})
    activation = dict(stream.get("gs470_30s_activation_truth") or {})
    last_tick = stream.get("last_tick_timestamp_ms")
    provider_event = getattr(type(provider), "_on_event", None)
    snapshot_client = getattr(provider, "_snapshot_client", None)
    sdk = getattr(snapshot_client, "sdk", None)
    sdk_stream = getattr(type(sdk), "stream", None) if sdk is not None else None
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
        "provider_event_hook_present": bool(
            getattr(provider_event, "_gs379_tick_aggregation", False)
            or getattr(provider_event, _PROVIDER_EVENT_OWNER, False)
        ),
        "sdk_tick_transport_hook_present": bool(
            getattr(sdk_stream, "_gs379_tick_transport", False)
            or getattr(sdk_stream, _SDK_STREAM_OWNER, False)
        ),
        "gs469_restart_count": _int(stream.get("gs469_stale_stream_restarts")),
        "gs469_restart_performed_last_check": bool(continuity.get("restart_performed")),
        "gs469_restart_reason_last_check": continuity.get("restart_reason"),
        "gs470_activation_performed": bool(activation.get("activation_performed")),
        "gs470_state_rehydrated": bool(activation.get("gs379_state_rehydrated")),
        "gs471_subscription_retired_for_rebind": bool(
            activation.get("subscription_retired_for_rebind")
        ),
        "runtime_hard_bind": True,
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
        _safe_activate(self)
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


def _active_recorder_globals() -> dict[str, Any]:
    """Use GS427's proven retained-function lookup instead of assuming module identity."""
    try:
        from . import gs427_flight_recorder_latency_hard_bind as gs427

        globals_dict = gs427._active_recorder_globals()
        if isinstance(globals_dict, dict):
            return globals_dict
    except Exception:
        pass
    from . import flight_recorder

    return flight_recorder.__dict__


def _install_hard_recorder_health() -> None:
    """Bind health to the exact persistence global reached by active record_scan."""
    from . import flight_recorder

    globals_dict = _active_recorder_globals()
    current = globals_dict.get("persist_replayable_scan")
    if not callable(current) or getattr(current, _HARD_RECORDER_OWNER, False):
        return

    @wraps(current)
    def persist_with_hard_bound_30s_health(recorder, scan: dict, records, *args, **kwargs):
        enriched = dict(scan or {})
        enriched["stream_30s_health"] = stream_30s_health(_active_or_last_provider())
        return current(recorder, enriched, records, *args, **kwargs)

    persist_with_hard_bound_30s_health._gs471_30s_health_hard_bind = True
    persist_with_hard_bound_30s_health._gs471_original = current
    setattr(persist_with_hard_bound_30s_health, _HARD_RECORDER_OWNER, True)
    globals_dict["persist_replayable_scan"] = persist_with_hard_bound_30s_health
    if globals_dict is flight_recorder.__dict__:
        flight_recorder.persist_replayable_scan = persist_with_hard_bound_30s_health


def _bind_context_class(context) -> None:
    """Activate every future provider assignment on the actual retained context class."""
    if context is None:
        return
    context_class = type(context)
    current = getattr(context_class, "__setattr__", None)
    if not callable(current) or getattr(current, _CONTEXT_SETATTR_OWNER, False):
        return

    @wraps(current)
    def context_setattr(self, name, value):
        current(self, name, value)
        if name == "provider_instance" and value is not None:
            _safe_activate(value)

    context_setattr._gs471_original = current
    setattr(context_setattr, _CONTEXT_SETATTR_OWNER, True)
    context_class.__setattr__ = context_setattr


def _install_scan_context_hard_bind() -> None:
    """Reach the actual retained provider before app.py starts its first quote cycle."""
    from . import completed_scan

    current = completed_scan.scan_context
    if getattr(current, _SCAN_CONTEXT_OWNER, False):
        return

    @wraps(current)
    def scan_context(state):
        context = current(state)
        _bind_context_class(context)
        provider = getattr(context, "provider_instance", None)
        if provider is not None:
            _safe_activate(provider)
        return context

    scan_context._gs471_original = current
    setattr(scan_context, _SCAN_CONTEXT_OWNER, True)
    completed_scan.scan_context = scan_context


def install() -> None:
    """Install clean-process wrappers plus retained-runtime hard bindings."""
    _install_activation_boundary()
    _install_recorder_health()
    _install_hard_recorder_health()
    _install_scan_context_hard_bind()

"""GS470/GS471: hard-bind genuine Webull 30-second truth across warm runtimes.

Flight Recorder #73 proved GS470's first clean-module wrapper never reached Walter's
retained Streamlit runtime: current build a41ab40b0aa1 produced 19 scans / 47 GS390
symbol observations with zero canonical 30s snapshots, and none of those scans carried
the promised ``stream_30s_health`` block. GS471 therefore applies the same retained-
function/object strategy already proven by GS427.

This remains market-data lifecycle / diagnostics only. Genuine Webull TICK is the only
30s source. There is no synthetic/history fallback and no change to discovery, scores,
VWAP/ST formulas, qualification, readiness, alerts, execution or orders.
"""
from __future__ import annotations

from collections import deque
from datetime import datetime, timezone
from functools import wraps
from typing import Any
import weakref

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
    if provider is None:
        return False
    snapshot = getattr(provider, "_snapshot_client", None)
    if _identity(snapshot) != ("mide.webull_live", "WebullOpenAPIClient"):
        return False
    sdk = getattr(snapshot, "sdk", None)
    if _identity(sdk) != ("mide.webull_sdk", "WebullSDKClient"):
        return False
    return (
        getattr(provider, "_stream_class", None) is None
        and getattr(provider, "_bootstrap", None) is None
    )


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
    """Create only missing observational state; never clear retained live bars."""
    lock = getattr(provider, "_lock", None)
    if lock is None:
        return False
    changed = False
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
    """Attach GS379 TRADE aggregation to the actual retained provider class."""
    from . import gs379_webull_stream_data_truth as gs379

    owner = type(provider)
    current = getattr(owner, "_on_event", None)
    if not callable(current):
        return False
    if getattr(current, "_gs379_tick_aggregation", False) or getattr(
        current, _PROVIDER_EVENT_OWNER, False
    ):
        if not callable(getattr(owner, "stream_30s_bars", None)):
            owner.stream_30s_bars = gs379._stream_30s_bars
        return False

    @wraps(current)
    def on_event(self, event: MarketEvent) -> None:
        _ensure_gs379_state(self)
        if event.type == EventType.TRADE:
            if event.symbol not in self._gs379_30s_closed:
                with self._lock:
                    self._gs379_30s_closed.setdefault(
                        event.symbol, deque(maxlen=THIRTY_SECOND_HISTORY)
                    )
            if not gs379._record_tick(self, event):
                return
            # TICK volume is trade size; preserve the existing snapshot cache's
            # cumulative-volume meaning while still letting base _on_event update price.
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
    owner._on_event = on_event
    owner.stream_30s_bars = gs379._stream_30s_bars
    return True


def _patch_retained_sdk_stream(provider) -> bool:
    """Attach official GS379 TICK transport to the actual retained SDK class."""
    from . import gs379_webull_stream_data_truth as gs379

    snapshot = getattr(provider, "_snapshot_client", None)
    sdk = getattr(snapshot, "sdk", None)
    data_client = getattr(sdk, "sdk_client", None)
    factory = getattr(data_client, "_walter_streaming_client_factory", None)
    owner = type(sdk) if sdk is not None else None
    current = getattr(owner, "stream", None) if owner is not None else None
    if not callable(current) or not callable(factory):
        return False
    if getattr(current, "_gs379_tick_transport", False) or getattr(
        current, _SDK_STREAM_OWNER, False
    ):
        return False

    @wraps(current)
    def stream(self, callback):
        active_factory = getattr(
            self.sdk_client, "_walter_streaming_client_factory", None
        )
        if not callable(active_factory):
            raise RuntimeError("Webull OpenAPI SDK lacks DataStreamingClient")
        return gs379.OfficialWebullTickTransport(active_factory(), callback)

    stream._gs379_tick_transport = True
    stream._gs471_original = current
    setattr(stream, _SDK_STREAM_OWNER, True)
    owner.stream = stream
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


def _retire_obsolete_subscription(
    provider, *, force: bool = False
) -> tuple[bool, str | None]:
    """Drop a captured old callback/dead TICK stream so normal init can reopen it."""
    if getattr(provider, "_subscription", None) is None:
        return False, None
    age = _tick_age_seconds(provider)
    if force:
        reason = "runtime 30s hook/activation changed; subscription callback must be rebound"
    elif age is None:
        reason = "subscribed Webull transport has no observed TICK heartbeat"
    elif age > STALE_TICK_SECONDS:
        reason = f"last Webull TICK heartbeat is {age:.1f}s old"
    else:
        return False, None

    from . import gs379_webull_stream_data_truth as gs379

    gs379._retire_provider_stream(provider)
    return True, reason


def activate_production_30s(provider) -> dict:
    """Hard-bind the actual production provider before its snapshot cycle."""
    from . import gs379_webull_stream_data_truth as gs379

    production = _production_sdk_graph(provider)
    stream = _stream_diagnostics(provider)
    enabled_before = bool(getattr(provider, "_enable_streaming", False)) if provider is not None else False
    state_rehydrated = enabled_now = rebound = False
    provider_event_patched = sdk_stream_patched = False
    retired = False
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
        retired, retirement_reason = _retire_obsolete_subscription(
            provider,
            force=bool(enabled_now or provider_event_patched or sdk_stream_patched),
        )
        _remember_provider(provider)

    truth = {
        "authority": AUTHORITY,
        "production_sdk_graph": production,
        "streaming_enabled_before": enabled_before,
        "streaming_enabled_now": bool(getattr(provider, "_enable_streaming", False)) if provider is not None else False,
        "activation_performed": enabled_now,
        "gs379_state_rehydrated": state_rehydrated,
        "active_provider_reasserted": rebound,
        "retained_provider_event_hook_patched": provider_event_patched,
        "retained_sdk_stream_hook_patched": sdk_stream_patched,
        "subscription_retired_for_rebind": retired,
        "subscription_retirement_reason": retirement_reason,
        "runtime_hard_bind": True,
        "genuine_webull_tick_only": True,
        "synthetic_30s_bars": False,
        "entry_authority_changed": False,
    }
    stream["gs470_30s_activation_truth"] = truth
    return dict(truth)


def _safe_activate(provider) -> dict:
    """An observational repair may never break the authoritative REST snapshot scan."""
    try:
        return activate_production_30s(provider)
    except Exception as exc:
        _stream_diagnostics(provider)["gs471_runtime_hard_bind_error"] = type(exc).__name__
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
    snapshot = getattr(provider, "_snapshot_client", None)
    sdk = getattr(snapshot, "sdk", None)
    data_client = getattr(sdk, "sdk_client", None)
    return callable(getattr(data_client, "_walter_streaming_client_factory", None))


def stream_30s_health(provider) -> dict:
    """Persist liveness truth even before the first 30s bar can close."""
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
    snapshot = getattr(provider, "_snapshot_client", None)
    sdk = getattr(snapshot, "sdk", None)
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
    """Locate the globals dictionary the retained record_scan actually invokes."""
    try:
        from . import gs427_flight_recorder_latency_hard_bind as gs427

        result = gs427._active_recorder_globals()
        if isinstance(result, dict):
            return result
    except Exception:
        pass
    from . import flight_recorder

    return flight_recorder.__dict__


def _install_hard_recorder_health() -> None:
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


def _bind_context_class(context) -> bool:
    """Activate future provider assignments on a mutable retained ScanContext class."""
    if context is None:
        return False
    owner = type(context)
    current = getattr(owner, "__setattr__", None)
    if not callable(current) or getattr(current, _CONTEXT_SETATTR_OWNER, False):
        return False

    @wraps(current)
    def context_setattr(self, name, value):
        current(self, name, value)
        if name == "provider_instance" and value is not None:
            _safe_activate(value)

    context_setattr._gs471_original = current
    setattr(context_setattr, _CONTEXT_SETATTR_OWNER, True)
    try:
        owner.__setattr__ = context_setattr
    except (AttributeError, TypeError):
        # Test/compatibility contexts may use immutable built-in classes such as
        # SimpleNamespace. The retained production ScanContext is a normal Python
        # dataclass and is patchable; an immutable compatibility class is simply read.
        return False
    return True


def _install_scan_context_hard_bind() -> None:
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

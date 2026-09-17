"""GS488: contain Webull OpenAPI rc105 connection-limit retry storms.

Flight Recorder #89 finally preserved the exact live transport failure through GS487:
Webull rejected repeated TICK-stream attempts with ``rc code: 105, msg: Connection
limit exceeded``.  Because ``initialize_quotes`` normally calls ``ensure_stream`` on
every 60-second scan whenever no subscription exists, that remote rejection was being
retried once per scan.

GS488 adds a narrow five-minute cooldown only after Webull explicitly reports a
connection-limit failure.  During that window Walter keeps the proven REST
snapshot/history path fully active but suppresses redundant MQTT reconnect attempts.
Unrelated stream failures retain the existing retry behavior, and an existing/healthy
subscription is never blocked.  The cooldown lives on the session-retained provider,
so ordinary Streamlit reruns preserve it without adding global account state.

Warm-deploy safety matters here: Walter may retain a provider from an older Python
class generation.  ``install_for_provider`` therefore wraps the exact provider object,
and ``install`` also hooks GS470/GS487 so retained providers are rebound when observed.

No discovery, market-data value, 30-second synthesis, indicator, VWAP/ST formula,
score, gate, ranking, qualification, alert, execution, session-entry, or order
authority is changed.
"""
from __future__ import annotations

from functools import wraps
import time
from typing import Any, Callable

AUTHORITY = "WEBULL_CONNECTION_LIMIT_CONTAINMENT"
COOLDOWN_SECONDS = 300.0
_OWNER = "_walter_gs488_connection_limit_backoff"
_PROVIDER_OWNER = "_walter_gs488_provider_instance_backoff"
_GS470_OWNER = "_walter_gs488_gs470_provider_bind"
_GS487_OWNER = "_walter_gs488_gs487_provider_bind"
_TRACE_OWNER = "_walter_gs488_stream_trace"


def _stream(provider) -> dict:
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


def _is_connection_limit(value: Any) -> bool:
    text = " ".join(str(value or "").split()).casefold()
    return "connection limit exceeded" in text or (
        "rc code: 105" in text and "limit" in text
    )


def _state(provider) -> dict:
    stream = _stream(provider)
    state = stream.get("gs488_connection_limit_backoff")
    if not isinstance(state, dict):
        state = {
            "authority": AUTHORITY,
            "active": False,
            "cooldown_seconds": COOLDOWN_SECONDS,
            "next_retry_epoch": None,
            "consecutive_limit_failures": 0,
            "suppressed_attempts": 0,
            "last_limit_failure": None,
            "rest_snapshot_history_unchanged": True,
            "genuine_webull_tick_only": True,
            "trading_authority_changed": False,
        }
        stream["gs488_connection_limit_backoff"] = state
    return state


def backoff_snapshot(provider, *, now: float | None = None) -> dict:
    if provider is None:
        return {
            "authority": AUTHORITY,
            "provider_present": False,
            "active": False,
            "cooldown_seconds": COOLDOWN_SECONDS,
            "next_retry_epoch": None,
            "seconds_remaining": None,
            "consecutive_limit_failures": 0,
            "suppressed_attempts": 0,
            "rest_snapshot_history_unchanged": True,
            "trading_authority_changed": False,
        }
    current = float(time.time() if now is None else now)
    state = dict(_state(provider))
    deadline = state.get("next_retry_epoch")
    try:
        remaining = max(0.0, float(deadline) - current) if deadline is not None else 0.0
    except (TypeError, ValueError):
        remaining = 0.0
    active = bool(
        getattr(provider, "_subscription", None) is None
        and remaining > 0.0
        and state.get("active")
    )
    state.update(
        provider_present=True,
        active=active,
        seconds_remaining=round(remaining, 1) if active else 0.0,
    )
    return state


def ensure_stream_with_backoff(
    original: Callable,
    provider,
    symbols,
    *,
    now: float | None = None,
):
    """Delegate once unless a recent explicit Webull connection-limit rejection exists."""
    current = float(time.time() if now is None else now)
    state = _state(provider)

    # A real live subscription always wins.  Backoff may never suppress upkeep of a
    # stream that actually recovered between scans.
    if getattr(provider, "_subscription", None) is not None:
        result = original(symbols)
        if result:
            state["active"] = False
            state["next_retry_epoch"] = None
            state["consecutive_limit_failures"] = 0
        return result

    deadline = state.get("next_retry_epoch")
    try:
        remaining = float(deadline) - current if deadline is not None else 0.0
    except (TypeError, ValueError):
        remaining = 0.0
    if bool(state.get("active")) and remaining > 0.0:
        state["suppressed_attempts"] = int(state.get("suppressed_attempts", 0) or 0) + 1
        state["last_suppressed_epoch"] = current
        return False

    stream = _stream(provider)
    failures_before = len(list(stream.get("subscription_failures") or []))
    result = original(symbols)
    failures = list(stream.get("subscription_failures") or [])
    newest = failures[-1] if len(failures) > failures_before else None

    if result:
        state["active"] = False
        state["next_retry_epoch"] = None
        state["consecutive_limit_failures"] = 0
        state["last_recovery_epoch"] = current
        return result

    if _is_connection_limit(newest):
        state["active"] = True
        state["cooldown_seconds"] = COOLDOWN_SECONDS
        state["next_retry_epoch"] = current + COOLDOWN_SECONDS
        state["consecutive_limit_failures"] = int(
            state.get("consecutive_limit_failures", 0) or 0
        ) + 1
        state["last_limit_failure"] = "WEBULL_RC105_CONNECTION_LIMIT"
        state["last_limit_failure_epoch"] = current
    else:
        # Do not broaden GS488 into a generic reconnect policy.  Existing behavior
        # remains authoritative for every failure class other than rc105/limit.
        state["active"] = False
        state["next_retry_epoch"] = None
    return result


def install_for_provider(provider) -> bool:
    """Patch the exact retained provider instance, regardless of class generation."""
    if provider is None:
        return False
    current = getattr(provider, "ensure_stream", None)
    if not callable(current):
        return False
    function = getattr(current, "__func__", current)
    if getattr(function, _OWNER, False) or getattr(current, _PROVIDER_OWNER, False):
        return False

    @wraps(current)
    def guarded(symbols):
        return ensure_stream_with_backoff(current, provider, symbols)

    setattr(guarded, _OWNER, True)
    setattr(guarded, _PROVIDER_OWNER, True)
    guarded._gs488_original = current
    try:
        provider.ensure_stream = guarded
    except (AttributeError, TypeError):
        return False
    _state(provider)
    return True


def _install_clean_class() -> None:
    from . import webull_live

    current = webull_live.LiveWebullProvider.ensure_stream
    if getattr(current, _OWNER, False):
        return

    @wraps(current)
    def ensure_stream(self, symbols):
        return ensure_stream_with_backoff(
            lambda active_symbols: current(self, active_symbols), self, symbols
        )

    setattr(ensure_stream, _OWNER, True)
    ensure_stream._gs488_original = current
    webull_live.LiveWebullProvider.ensure_stream = ensure_stream


def _install_retained_activation_bind() -> None:
    from . import gs470_30s_activation_truth as gs470

    current = gs470._safe_activate
    if getattr(current, _GS470_OWNER, False):
        return

    @wraps(current)
    def safe_activate(provider):
        install_for_provider(provider)
        return current(provider)

    setattr(safe_activate, _GS470_OWNER, True)
    safe_activate._gs488_original = current
    gs470._safe_activate = safe_activate


def _install_recorder_provider_bind() -> None:
    # app.py dynamically resolves GS487 immediately before every recorder write.
    # That gives warm deployments a reliable exact-provider foothold for the *next*
    # scan even when the provider class itself predates GS488.
    from . import gs427_flight_recorder_latency_hard_bind as gs427
    from . import gs487_cached_recorder_instance_bind as gs487

    current = gs487.install_for_recorder
    if getattr(current, _GS487_OWNER, False):
        return

    @wraps(current)
    def install_for_recorder(recorder):
        provider, _provider_source = gs427._active_provider()
        install_for_provider(provider)
        return current(recorder)

    setattr(install_for_recorder, _GS487_OWNER, True)
    install_for_recorder._gs488_original = current
    gs487.install_for_recorder = install_for_recorder


def _install_stream_trace() -> None:
    from . import gs481_live_evidence_hard_bind as gs481

    current = gs481._stream_failure_truth
    if getattr(current, _TRACE_OWNER, False):
        return

    @wraps(current)
    def stream_failure_truth(provider):
        truth = dict(current(provider) or {})
        truth["connection_limit_backoff"] = backoff_snapshot(provider)
        truth["gs488_connection_limit_containment"] = True
        return truth

    setattr(stream_failure_truth, _TRACE_OWNER, True)
    stream_failure_truth._gs488_original = current
    gs481._stream_failure_truth = stream_failure_truth


def install() -> None:
    """Install clean-process and retained-provider connection-limit containment."""
    _install_clean_class()
    _install_retained_activation_bind()
    _install_recorder_provider_bind()
    _install_stream_trace()

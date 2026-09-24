"""GS470/GS471: warm-deploy-safe split authority facade for genuine Webull 30s truth.

Market Evidence owns retained-provider activation, genuine TICK lifecycle truth,
stream-health measurement and ScanContext hard binding. Replay / Validation owns
Flight Recorder persistence of that health truth.

This historical module intentionally retains mutable compatibility seams such as
_safe_activate because GS488 wraps that exact symbol at runtime, plus retained-provider
weakref memory so a warm module generation does not lose the last known provider.
Authority installers resolve lazily and safely no-op when a stale generation lacks a
newer export.

No synthetic/history 30s fallback or trading-authority behavior is introduced.
"""
from __future__ import annotations

from typing import Any
import weakref


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

CONTRACT = {
    "genuine_webull_tick_only": True,
    "synthetic_30s_bars": False,
}


def _market():
    from mide.authorities import market_evidence

    return market_evidence


def _replay():
    from mide.authorities import replay_validation

    return replay_validation


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
    current = getattr(
        _market(),
        "activate_production_30s_evidence",
        None,
    )
    if not callable(current):
        return {
            "authority": AUTHORITY,
            "production_sdk_graph": False,
            "runtime_hard_bind": True,
            "activation_error": "authority_generation_unavailable",
            "genuine_webull_tick_only": True,
            "synthetic_30s_bars": False,
            "entry_authority_changed": False,
        }
    return current(provider)


def _safe_activate(provider) -> dict:
    current = getattr(
        _market(),
        "safe_activate_production_30s",
        None,
    )
    if callable(current):
        return current(provider)
    return activate_production_30s(provider)


def stream_30s_health(provider) -> dict:
    current = getattr(_market(), "production_30s_health", None)
    if not callable(current):
        return {
            "authority": AUTHORITY,
            "provider_present": provider is not None,
            "runtime_hard_bind": True,
            "genuine_webull_tick_only": True,
            "synthetic_30s_bars": False,
        }
    return current(provider)


def _active_or_last_provider():
    current = getattr(
        _market(),
        "active_or_last_30s_provider",
        None,
    )
    if callable(current):
        return current()
    return _last_provider()


def _install_activation_boundary() -> None:
    current = getattr(
        _market(),
        "install_production_30s_activation_boundary",
        None,
    )
    if callable(current):
        current()


def _bind_context_class(context) -> bool:
    current = getattr(
        _market(),
        "bind_production_30s_context_class",
        None,
    )
    if not callable(current):
        return False
    return current(context)


def _install_scan_context_hard_bind() -> None:
    current = getattr(
        _market(),
        "install_production_30s_scan_context_hard_bind",
        None,
    )
    if callable(current):
        current()


def _active_recorder_globals() -> dict[str, Any]:
    current = getattr(
        _replay(),
        "active_30s_recorder_globals",
        None,
    )
    if callable(current):
        return current()
    from mide import flight_recorder

    return flight_recorder.__dict__


def _install_recorder_health() -> None:
    current = getattr(
        _replay(),
        "install_30s_recorder_health",
        None,
    )
    if callable(current):
        current()


def _install_hard_recorder_health() -> None:
    current = getattr(
        _replay(),
        "install_30s_hard_recorder_health",
        None,
    )
    if callable(current):
        current()


def install() -> None:
    _install_activation_boundary()
    _install_recorder_health()
    _install_hard_recorder_health()
    _install_scan_context_hard_bind()


def __getattr__(name: str):
    try:
        return getattr(_market(), name)
    except AttributeError:
        try:
            return getattr(_replay(), name)
        except AttributeError:
            raise AttributeError(name) from None


__all__ = [
    "AUTHORITY",
    "THIRTY_SECOND_HISTORY",
    "STALE_TICK_SECONDS",
    "activate_production_30s",
    "stream_30s_health",
    "install",
]

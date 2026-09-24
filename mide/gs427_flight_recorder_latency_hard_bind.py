"""GS427/GS472: warm-deploy-safe Replay / Validation facade.

Replay / Validation owns active-recorder graph discovery, runtime build identity,
latency persistence, and the bounded GS472 retained-provider self-heal telemetry.
This historical module remains the shared compatibility seam used by GS470,
GS480/481, GS484-488, GS502 and the regression suite.

The helper functions intentionally remain mutable delegates because later hard-bind
layers monkeypatch _active_recorder_globals, _active_provider, _runtime_identity and
_provider_health. Replay / Validation's installer calls back through these historical
names at runtime so those validated seams remain effective.

Recorder self-heal never starts a subscription here:
"network_subscription_started_here": False
and genuine Webull TICK remains the only 30-second source:
"genuine_webull_tick_only": True

No discovery, market-data value, indicator, gate, score, threshold, qualification,
ranking, audio, execution, session authority, or order behavior changes.
"""
from __future__ import annotations

from types import FunctionType
from typing import Any


AUTHORITY = "OBSERVATIONAL_ONLY"
_BINDING_NAME = (
    "FlightRecorder.record_scan.__globals__.persist_replayable_scan"
)
_INSTALL_GENERATION = object()


def _replay():
    from mide.authorities import replay_validation

    return replay_validation


def _walk_functions(root) -> list[FunctionType]:
    current = getattr(
        _replay(),
        "recorder_runtime_walk_functions",
        None,
    )
    if not callable(current):
        return [root] if isinstance(root, FunctionType) else []
    return current(root)


def _active_recorder_globals() -> dict[str, Any]:
    current = getattr(
        _replay(),
        "active_recorder_globals",
        None,
    )
    if callable(current):
        return current()
    from mide import flight_recorder

    return flight_recorder.__dict__


def _remember_active_provider(provider) -> None:
    current = getattr(
        _replay(),
        "remember_recorder_active_provider",
        None,
    )
    if callable(current):
        current(provider)


def _remembered_active_provider():
    current = getattr(
        _replay(),
        "remembered_recorder_active_provider",
        None,
    )
    if not callable(current):
        return None
    return current()


def _heal_active_provider(provider) -> dict[str, Any]:
    current = getattr(
        _replay(),
        "heal_recorder_active_provider",
        None,
    )
    if not callable(current):
        return {}
    return current(provider)


def _provider_health(provider) -> dict[str, Any]:
    current = getattr(
        _replay(),
        "recorder_provider_health",
        None,
    )
    if not callable(current):
        return {
            "provider_present": provider is not None,
            "gs472_recorder_provider_self_heal": False,
            "network_subscription_started_here": False,
            "genuine_webull_tick_only": True,
            "synthetic_30s_bars": False,
        }
    return current(provider)


def _active_provider():
    current = getattr(
        _replay(),
        "recorder_active_provider",
        None,
    )
    if not callable(current):
        return None, "unavailable"
    return current()


def _runtime_identity(
    provider_source: str,
) -> dict[str, Any]:
    current = getattr(
        _replay(),
        "recorder_runtime_identity",
        None,
    )
    if not callable(current):
        return {
            "authority": AUTHORITY,
            "gs427_hard_bind": True,
            "gs472_provider_self_heal": False,
            "binding": _BINDING_NAME,
            "provider_source": provider_source,
            "trading_logic_changed": False,
        }
    return current(provider_source)


def install() -> None:
    current = getattr(
        _replay(),
        "install_recorder_runtime_hard_bind",
        None,
    )
    if callable(current):
        current()


def __getattr__(name: str):
    try:
        return getattr(_replay(), name)
    except AttributeError:
        raise AttributeError(name) from None


__all__ = [
    "AUTHORITY",
    "_walk_functions",
    "_active_recorder_globals",
    "_active_provider",
    "_runtime_identity",
    "_provider_health",
    "install",
]

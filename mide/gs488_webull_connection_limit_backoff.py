"""GS488: warm-deploy-safe split authority facade for Webull rc105 containment.

Market Evidence owns the rc105 retry/backoff lifecycle plus clean/retained provider
binding. Replay / Validation owns only the observational stream-failure trace
augmentation.

The historical helper names remain mutable compatibility seams. In particular,
Market Evidence intentionally defines and uses a module-global ensure_stream_with_backoff
inside installed wrappers so GS489 can keep upgrading retained/new GS488 wrappers
in place by replacing that exact global name.

Scope-lock contract remains:
COOLDOWN_SECONDS = 300.0
BACKOFF_SECONDS = (300.0, 600.0, 900.0)
REVISION = 2
rest_snapshot_history_unchanged remains true and
"trading_authority_changed": False remains true.

No discovery, market-data value, 30-second synthesis, indicator, VWAP/ST formula,
score, gate, ranking, qualification, alert, execution, session-entry, or order
authority is changed.
"""
from __future__ import annotations

from typing import Any, Callable


AUTHORITY = "WEBULL_CONNECTION_LIMIT_CONTAINMENT"
COOLDOWN_SECONDS = 300.0
BACKOFF_SECONDS = (300.0, 600.0, 900.0)
_OWNER = "_walter_gs488_connection_limit_backoff"
_PROVIDER_OWNER = "_walter_gs488_provider_instance_backoff"
_GS470_OWNER = "_walter_gs488_gs470_provider_bind"
_GS487_OWNER = "_walter_gs488_gs487_provider_bind"
_TRACE_OWNER = "_walter_gs488_stream_trace"
REVISION = 2


def _market():
    from mide.authorities import market_evidence

    return market_evidence


def _replay():
    from mide.authorities import replay_validation

    return replay_validation


def _stream(provider) -> dict:
    current = getattr(
        _market(),
        "connection_limit_stream",
        None,
    )
    if not callable(current):
        return {}
    return current(provider)


def _is_connection_limit(value: Any) -> bool:
    current = getattr(
        _market(),
        "connection_limit_rejection",
        None,
    )
    return bool(
        current(value)
        if callable(current)
        else False
    )


def _cooldown_for_failures(
    failures: Any,
) -> float:
    current = getattr(
        _market(),
        "connection_limit_cooldown",
        None,
    )
    if not callable(current):
        return COOLDOWN_SECONDS
    return float(current(failures))


def _state(provider) -> dict:
    current = getattr(
        _market(),
        "connection_limit_state",
        None,
    )
    if not callable(current):
        return {
            "authority": AUTHORITY,
            "active": False,
            "cooldown_seconds": COOLDOWN_SECONDS,
            "backoff_schedule_seconds": list(
                BACKOFF_SECONDS
            ),
            "rest_snapshot_history_unchanged": True,
            "trading_authority_changed": False,
        }
    return current(provider)


def _refresh_active_deadline(
    provider,
    *,
    now: float,
) -> dict:
    current = getattr(
        _market(),
        "refresh_connection_limit_deadline",
        None,
    )
    if not callable(current):
        return _state(provider)
    return current(provider, now=now)


def backoff_snapshot(
    provider,
    *,
    now: float | None = None,
) -> dict:
    current = getattr(
        _market(),
        "connection_limit_backoff_snapshot",
        None,
    )
    if not callable(current):
        return _state(provider)
    return current(provider, now=now)


def ensure_stream_with_backoff(
    original: Callable,
    provider,
    symbols,
    *,
    now: float | None = None,
):
    current = getattr(
        _market(),
        "ensure_stream_with_backoff",
        None,
    )
    if not callable(current):
        return original(symbols)
    return current(
        original,
        provider,
        symbols,
        now=now,
    )


def _upgrade_wrapper_global(
    function,
    name: str,
    value: Any,
) -> bool:
    current = getattr(
        _market(),
        "upgrade_connection_limit_wrapper_global",
        None,
    )
    if not callable(current):
        return False
    return bool(
        current(function, name, value)
    )


def install_for_provider(provider) -> bool:
    current = getattr(
        _market(),
        "install_for_provider",
        None,
    )
    if not callable(current):
        return False
    return bool(current(provider))


def _install_clean_class() -> None:
    current = getattr(
        _market(),
        "install_connection_limit_clean_class",
        None,
    )
    if callable(current):
        current()


def _install_retained_activation_bind() -> None:
    current = getattr(
        _market(),
        "install_connection_limit_activation_bind",
        None,
    )
    if callable(current):
        current()


def _install_recorder_provider_bind() -> None:
    current = getattr(
        _market(),
        "install_connection_limit_recorder_bind",
        None,
    )
    if callable(current):
        current()


def _install_stream_trace() -> None:
    current = getattr(
        _replay(),
        "install_connection_limit_stream_trace",
        None,
    )
    if callable(current):
        current()


def install() -> None:
    current = getattr(
        _market(),
        "install_connection_limit_market_evidence",
        None,
    )
    if callable(current):
        current()
    _install_stream_trace()


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
    "COOLDOWN_SECONDS",
    "BACKOFF_SECONDS",
    "REVISION",
    "backoff_snapshot",
    "ensure_stream_with_backoff",
    "install_for_provider",
    "install",
]

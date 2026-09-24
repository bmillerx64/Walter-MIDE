"""GS489: warm-deploy-safe Market Evidence facade for graduated rc105 backoff.

Market Evidence owns the 5/10/15-minute Webull connection-limit cadence and retained
provider upgrade. This historical module remains the app-entry compatibility surface
and intentionally retains its imported time module: Market Evidence resolves
gs489.time.time() for every implicit clock read, preserving the established monkeypatch
seam exactly.

A retained GS488 wrapper is still upgraded in place by replacing its referenced global
name ensure_stream_with_backoff. No second retry wrapper is nested around that retained
function.

Scope contract remains:
BACKOFF_SECONDS = (300.0, 600.0, 900.0)
rest_snapshot_history_unchanged remains true and
"trading_authority_changed": False remains true.

REST snapshots/history, genuine Webull TICK-only 30s truth, discovery, indicators,
VWAP/ST, scoring, gates, ranking, qualification, alerts, execution and orders are
unchanged.
"""
from __future__ import annotations

import time
from typing import Any, Callable


AUTHORITY = "WEBULL_CONNECTION_LIMIT_GRADUATED_BACKOFF"
BACKOFF_SECONDS = (300.0, 600.0, 900.0)
_STATE_KEY = "gs488_connection_limit_backoff"
_GS488_OWNER = "_walter_gs488_connection_limit_backoff"
_GS489_OWNER = "_walter_gs489_graduated_backoff_revision"
REVISION = 1


def _market():
    from mide.authorities import market_evidence

    return market_evidence


def _stream(provider) -> dict:
    current = getattr(
        _market(),
        "connection_limit_stream",
        None,
    )
    if not callable(current):
        return {}
    return current(provider)


def _state(provider) -> dict:
    current = getattr(
        _market(),
        "graduated_backoff_state",
        None,
    )
    if not callable(current):
        return {
            "authority": "WEBULL_CONNECTION_LIMIT_CONTAINMENT",
            "active": False,
            "cooldown_seconds": BACKOFF_SECONDS[0],
            "next_retry_epoch": None,
            "consecutive_limit_failures": 0,
            "suppressed_attempts": 0,
            "last_limit_failure": None,
            "rest_snapshot_history_unchanged": True,
            "genuine_webull_tick_only": True,
            "trading_authority_changed": False,
        }
    return current(provider)


def _is_connection_limit(value: Any) -> bool:
    current = getattr(
        _market(),
        "graduated_connection_limit_rejection",
        None,
    )
    return bool(
        current(value)
        if callable(current)
        else False
    )


def _cooldown_for_failures(
    value: Any,
) -> float:
    current = getattr(
        _market(),
        "graduated_backoff_cooldown",
        None,
    )
    if not callable(current):
        return BACKOFF_SECONDS[0]
    return float(current(value))


def _refresh_active_deadline(
    provider,
    *,
    now: float,
) -> dict:
    current = getattr(
        _market(),
        "refresh_graduated_backoff_deadline",
        None,
    )
    if not callable(current):
        return _state(provider)
    return current(provider, now=now)


def ensure_stream_with_graduated_backoff(
    original: Callable,
    provider,
    symbols,
    *,
    now: float | None = None,
):
    current = getattr(
        _market(),
        "ensure_stream_with_graduated_backoff",
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


def install_for_provider(provider) -> bool:
    current = getattr(
        _market(),
        "install_graduated_backoff_for_provider",
        None,
    )
    if not callable(current):
        return False
    return bool(current(provider))


def __getattr__(name: str):
    try:
        return getattr(_market(), name)
    except AttributeError:
        raise AttributeError(name) from None


__all__ = [
    "AUTHORITY",
    "BACKOFF_SECONDS",
    "REVISION",
    "ensure_stream_with_graduated_backoff",
    "install_for_provider",
]

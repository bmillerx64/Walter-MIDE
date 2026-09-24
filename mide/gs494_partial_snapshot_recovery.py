"""GS494: warm-deploy-safe Market Evidence facade for partial snapshot recovery.

Market Evidence owns the one bounded official-Webull retry for symbols omitted from a
partially successful snapshot batch. This historical module remains the app-entry
compatibility surface and preserves its helper/install names for retained providers.

The nested retry still targets the captured pre-GS494 initialize_quotes callable, so
recursion is impossible and the maximum extra provider request remains one. Persistent
omissions remain unavailable and fail closed.

Scope contract remains:
stale_price_substitution is false.
extra_provider_requests_max is at most one.
"trading_authority_changed": False remains true.

No cached/stale price is manufactured, no synthetic 30s source is added, and no
discovery, indicator, score, ranking, qualification, readiness, anti-chase, alert,
execution or order rule changes.
"""
from __future__ import annotations

from typing import Callable, Iterable


_OWNER = "_walter_gs494_partial_snapshot_recovery"
REVISION = 1


def _market():
    from mide.authorities import market_evidence

    return market_evidence


def _symbols(
    values: Iterable[str],
) -> list[str]:
    current = getattr(
        _market(),
        "partial_snapshot_symbols",
        None,
    )
    if not callable(current):
        return list(
            dict.fromkeys(
                str(value or "").strip().upper()
                for value in values or []
                if str(value or "").strip()
            )
        )
    return current(values)


def initialize_quotes_with_partial_retry(
    original: Callable,
    provider,
    symbols: Iterable[str],
    *,
    batch_size: int,
):
    current = getattr(
        _market(),
        "initialize_quotes_with_partial_retry",
        None,
    )
    if not callable(current):
        return original(
            list(symbols),
            batch_size=batch_size,
        )
    return current(
        original,
        provider,
        symbols,
        batch_size=batch_size,
    )


def install_for_provider(provider) -> bool:
    current = getattr(
        _market(),
        "install_partial_snapshot_recovery_for_provider",
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
    "REVISION",
    "initialize_quotes_with_partial_retry",
    "install_for_provider",
]

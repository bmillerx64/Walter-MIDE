"""GS469: warm-deploy-safe Market Evidence facade for live 30-second continuity.

The stream-continuity meaning now lives in Market Evidence. This historical module
retains the validated constants, install point and private compatibility seam used by
the regression suite. Authority resolution is lazy so a stale warm Streamlit
generation can retain its already-installed wrapper instead of failing startup.

The only 30s source remains genuine Webull OpenAPI TICK data. No synthetic/history
fallback, trading threshold, qualification, readiness, execution or order behavior
is introduced.
"""
from __future__ import annotations

from datetime import time


AUTHORITY = "LIVE_30S_STREAM_CONTINUITY"
STALE_TICK_SECONDS = 180.0
RESTART_COOLDOWN_SECONDS = 300.0
STREAM_START_ET = time(4, 0)
STREAM_END_ET = time(20, 0)
_OWNER_ATTR = "_walter_gs469_30s_stream_continuity_owner"

CONTRACT = {"synthetic_30s_bars": False}


def _market():
    from mide.authorities import market_evidence

    return market_evidence


def _active_registry_provider():
    current = getattr(
        _market(),
        "active_30s_registry_provider",
        None,
    )
    if not callable(current):
        return None
    return current()


def reassert_active_provider(provider) -> bool:
    current = getattr(
        _market(),
        "reassert_active_30s_provider",
        None,
    )
    if not callable(current):
        return False
    return current(provider)


def ensure_stream_continuity(
    original,
    provider,
    symbols,
    *,
    now=None,
):
    current = getattr(
        _market(),
        "ensure_live_30s_stream_continuity",
        None,
    )
    if not callable(current):
        return original(provider, symbols)
    return current(
        original,
        provider,
        symbols,
        now=now,
    )


def install() -> None:
    current = getattr(
        _market(),
        "install_live_30s_stream_continuity",
        None,
    )
    if callable(current):
        current()


def __getattr__(name: str):
    try:
        return getattr(_market(), name)
    except AttributeError:
        raise AttributeError(name) from None


__all__ = [
    "AUTHORITY",
    "STALE_TICK_SECONDS",
    "RESTART_COOLDOWN_SECONDS",
    "STREAM_START_ET",
    "STREAM_END_ET",
    "reassert_active_provider",
    "ensure_stream_continuity",
    "install",
]

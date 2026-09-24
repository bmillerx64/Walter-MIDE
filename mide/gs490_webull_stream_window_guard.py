"""GS490: warm-deploy-safe Market Evidence facade for Webull TICK initiation.

Market Evidence owns the weekday 04:00 <= ET < 20:00 new-connection guard. This
historical module remains the app-entry compatibility surface and retains the validated
constants/helper names used by regression tests.

The guard still blocks only creation of a new TICK subscription outside the allowed
window. Existing subscriptions are not retired. REST snapshots/history/news continue.

Scope contract remains:
STREAM_START_ET = time(4, 0)
STREAM_END_ET = time(20, 0)
rest_snapshot_history_unchanged remains true and
"trading_authority_changed": False remains true.

No discovery, market-data values, synthetic 30s data, indicators, VWAP/ST formulas,
scores, gates, ranking, qualification, alerts, execution, or orders are changed.
"""
from __future__ import annotations

from datetime import datetime, time
from typing import Callable


AUTHORITY = "WEBULL_TICK_INITIATION_WINDOW"
STREAM_START_ET = time(4, 0)
STREAM_END_ET = time(20, 0)
BYPASS_REASON = (
    "Outside Webull 04:00-20:00 ET TICK initiation window"
)
_OWNER = "_walter_gs490_stream_window_guard"
REVISION = 1


def _market():
    from mide.authorities import market_evidence

    return market_evidence


def _utc(
    value: datetime | None = None,
) -> datetime:
    current = getattr(
        _market(),
        "webull_tick_window_utc",
        None,
    )
    if not callable(current):
        from datetime import timezone

        if value is None:
            return datetime.now(timezone.utc)
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    return current(value)


def stream_window_open(
    value: datetime | None = None,
) -> bool:
    current = getattr(
        _market(),
        "webull_tick_stream_window_open",
        None,
    )
    if not callable(current):
        return False
    return bool(current(value))


def _stream(provider) -> dict:
    current = getattr(
        _market(),
        "webull_tick_window_stream",
        None,
    )
    if not callable(current):
        return {}
    return current(provider)


def ensure_stream_in_window(
    original: Callable,
    provider,
    symbols,
    *,
    now: datetime | None = None,
):
    current = getattr(
        _market(),
        "ensure_stream_in_window",
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
        "install_stream_window_for_provider",
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
    "STREAM_START_ET",
    "STREAM_END_ET",
    "BYPASS_REASON",
    "REVISION",
    "stream_window_open",
    "ensure_stream_in_window",
    "install_for_provider",
]

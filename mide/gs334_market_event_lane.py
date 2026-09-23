"""Compatibility facade for Walter Next native market-awareness lane.

Market Evidence owns GS334's native Day Gainer evidence/capture and durable
completed-scan snapshot. Presentation + Audio owns duplicate suppression, actionable
symbol tracking, markup, and header rendering.
"""

from __future__ import annotations

from .authorities import market_evidence as _market
from .authorities import presentation_audio as _presentation


EXTREME_MOVER_PCT = _market.EXTREME_MOVER_PCT
MARKET_EVENT_LIMIT = _market.MARKET_EVENT_LIMIT

# Shared mutable compatibility views. Authoritative owners mutate these in place so
# historical readers continue to see the current cache without owning it.
_LATEST_MARKET_EVENTS = _market._LATEST_MARKET_EVENTS
_LATEST_ACTIONABLE_SYMBOLS = _presentation._LATEST_ACTIONABLE_SYMBOLS

market_event_rows = _market.market_event_rows
completed_scan_market_events = _market.completed_scan_market_events
visible_market_events = _presentation.visible_market_events
market_event_markup = _presentation.market_event_markup


def install() -> None:
    _market.install_market_event_capture()
    _presentation.install_market_event_presentation()


__all__ = [
    "EXTREME_MOVER_PCT",
    "MARKET_EVENT_LIMIT",
    "market_event_rows",
    "completed_scan_market_events",
    "visible_market_events",
    "market_event_markup",
    "install",
]

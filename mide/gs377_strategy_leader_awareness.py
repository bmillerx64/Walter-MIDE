"""Compatibility facade for GS377 strategy-leader market awareness."""

from __future__ import annotations

from .authorities import market_evidence as _market


STRATEGY_LEADER_MIN_GAIN_PCT = _market.STRATEGY_LEADER_MIN_GAIN_PCT
STRATEGY_LEADER_MAX_DAY_GAINER_RANK = _market.STRATEGY_LEADER_MAX_DAY_GAINER_RANK
STRATEGY_LEADER_PRICE_CEILING = _market.STRATEGY_LEADER_PRICE_CEILING
STRATEGY_LEADER_LIMIT = _market.STRATEGY_LEADER_LIMIT

implied_previous_close = _market.implied_previous_close
strategy_leader_rows = _market.strategy_leader_rows
merge_strategy_leader_events = _market.merge_strategy_leader_events


def publish_strategy_leader_awareness(provider, native_rows):
    """Delegate to Market Evidence and preserve the historical GS334 cache view."""
    from . import gs334_market_event_lane as lane

    combined = _market.publish_strategy_leader_awareness(provider, native_rows)
    cache = getattr(lane, "_LATEST_MARKET_EVENTS", None)
    if isinstance(cache, list) and cache is not _market._LATEST_MARKET_EVENTS:
        cache.clear()
        cache.extend(dict(event) for event in combined)
    return combined


def install() -> None:
    _market.install_strategy_leader_awareness()


__all__ = [
    "STRATEGY_LEADER_MIN_GAIN_PCT",
    "STRATEGY_LEADER_MAX_DAY_GAINER_RANK",
    "STRATEGY_LEADER_PRICE_CEILING",
    "STRATEGY_LEADER_LIMIT",
    "implied_previous_close",
    "strategy_leader_rows",
    "merge_strategy_leader_events",
    "publish_strategy_leader_awareness",
    "install",
]

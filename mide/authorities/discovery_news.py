"""Authoritative Walter Next Discovery + News boundary.

Legacy discovery/news behavior remains the execution source while consolidation
continues. Replaceable functions resolve dynamically so Streamlit warm reruns and
later compatibility installers cannot leave this authority holding stale callables.
Provider classes remain stable imports.
"""

from __future__ import annotations

from mide.news_provider import (
    MarketDataNewsProvider,
    NewsService,
    UnavailableNewsProvider,
)


def build_seed_symbols(*args, **kwargs):
    from mide import discovery
    return discovery.build_seed_symbols(*args, **kwargs)


def is_valid_us_symbol(*args, **kwargs):
    from mide import discovery
    return discovery.is_valid_us_symbol(*args, **kwargs)


def prefilter_snapshots(*args, **kwargs):
    from mide import discovery
    return discovery.prefilter_snapshots(*args, **kwargs)


def snapshot_identity_records(*args, **kwargs):
    from mide import discovery
    return discovery.snapshot_identity_records(*args, **kwargs)


def index_news(*args, **kwargs):
    from mide import news
    return news.index_news(*args, **kwargs)


def symbol_news_evidence(*args, **kwargs):
    from mide import news_provider
    return news_provider.symbol_news_evidence(*args, **kwargs)


def ticker_inspection(*args, **kwargs):
    from mide import news_provider
    return news_provider.ticker_inspection(*args, **kwargs)


__all__ = [
    "MarketDataNewsProvider",
    "NewsService",
    "UnavailableNewsProvider",
    "build_seed_symbols",
    "index_news",
    "is_valid_us_symbol",
    "prefilter_snapshots",
    "snapshot_identity_records",
    "symbol_news_evidence",
    "ticker_inspection",
]

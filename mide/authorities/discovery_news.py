"""Authority boundary for Discovery + News.

Phase 1 is a zero-semantics-change facade.  The validated legacy implementations
remain the execution source until their behavior is absorbed here deliberately.
"""

from mide.discovery import (
    build_seed_symbols,
    is_valid_us_symbol,
    prefilter_snapshots,
    snapshot_identity_records,
)
from mide.news import index_news
from mide.news_provider import (
    MarketDataNewsProvider,
    NewsService,
    UnavailableNewsProvider,
    symbol_news_evidence,
    ticker_inspection,
)

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

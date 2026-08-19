"""GS300: cover busy FMP Stock News tapes beyond page zero.

GS298 added market-wide news-first discovery but intentionally read only the newest
100 FMP Stock News rows. GS299 keeps a catalyst alive after Walter has seen it,
but cannot help when a valid six-hour catalyst has already been pushed off page 0
before Walter's first scan.

GS300 replaces only the market-wide discovery fetch with bounded pagination. It
uses the same entitled ``news/stock`` endpoint, freshness window, normalization,
and downstream material-catalyst selection. No scoring, qualification, ranking,
readiness, trigger, order, or execution semantics are changed.
"""
from __future__ import annotations

from datetime import timedelta

import requests

from .gs298_news_seeded_discovery import (
    NEWS_FEED_LIMIT,
    NEWS_SEED_FRESHNESS,
    _now_utc,
)

NEWS_FEED_MAX_PAGES = 3


def fetch_marketwide_stock_news_paginated(
    api_key: str,
    *,
    now=None,
    session=None,
    timeout: int = 4,
    limit: int = NEWS_FEED_LIMIT,
    max_pages: int = NEWS_FEED_MAX_PAGES,
):
    """Return up to three pages of fresh entitled FMP Stock News.

    Page 0 is authoritative: if it fails, the caller gets the existing GS298
    failure behavior and falls back to native Webull discovery. If a deeper page
    fails after page 0 succeeded, already-retrieved news is preserved rather than
    discarding useful evidence.
    """
    from .news_provider import FMPNewsProvider

    key = str(api_key or "").strip()
    if not key:
        fetch_marketwide_stock_news_paginated.last_pages_requested = 0
        fetch_marketwide_stock_news_paginated.last_raw_rows_seen = 0
        fetch_marketwide_stock_news_paginated.last_page_failures = 0
        return []

    endpoint = "news/stock"
    entitled = tuple(getattr(FMPNewsProvider, "ENTITLED_ENDPOINTS", (endpoint,)))
    if endpoint not in entitled:
        fetch_marketwide_stock_news_paginated.last_pages_requested = 0
        fetch_marketwide_stock_news_paginated.last_raw_rows_seen = 0
        fetch_marketwide_stock_news_paginated.last_page_failures = 0
        return []

    current = _now_utc(now)
    since = current - NEWS_SEED_FRESHNESS
    client = session or requests.Session()
    page_size = max(1, min(int(limit), NEWS_FEED_LIMIT))
    page_cap = max(1, min(int(max_pages), NEWS_FEED_MAX_PAGES))

    articles = []
    seen = set()
    pages_requested = 0
    raw_rows_seen = 0
    page_failures = 0

    for page in range(page_cap):
        params = {
            "from": since.date().isoformat(),
            "to": current.date().isoformat(),
            "page": page,
            "limit": page_size,
            "apikey": key,
        }
        pages_requested += 1
        try:
            response = client.get(
                f"{FMPNewsProvider.BASE_URL}/{endpoint}",
                params=params,
                timeout=timeout,
            )
            response.raise_for_status()
            payload = response.json()
        except Exception:
            page_failures += 1
            if page == 0:
                raise
            break

        rows = payload if isinstance(payload, list) else (
            payload.get("data", []) if isinstance(payload, dict) else []
        )
        if not rows:
            break
        raw_rows_seen += len(rows)

        for row in rows:
            article = FMPNewsProvider._normalize(row, endpoint=endpoint)
            if article is None:
                continue
            if not (since <= article.created_at <= current + timedelta(minutes=5)):
                continue
            identity = (article.provider.casefold(), str(article.id))
            if identity in seen:
                continue
            seen.add(identity)
            articles.append(article)

        # A short page proves there is no next full page to retrieve. Otherwise
        # continue to the explicit cap; do not assume provider sort order when
        # deciding whether a six-hour story could exist deeper in the feed.
        if len(rows) < page_size:
            break

    fetch_marketwide_stock_news_paginated.last_pages_requested = pages_requested
    fetch_marketwide_stock_news_paginated.last_raw_rows_seen = raw_rows_seen
    fetch_marketwide_stock_news_paginated.last_page_failures = page_failures
    fetch_marketwide_stock_news_paginated.last_articles_returned = len(articles)
    return articles


fetch_marketwide_stock_news_paginated.last_pages_requested = 0
fetch_marketwide_stock_news_paginated.last_raw_rows_seen = 0
fetch_marketwide_stock_news_paginated.last_page_failures = 0
fetch_marketwide_stock_news_paginated.last_articles_returned = 0


def install() -> None:
    """Install pagination into GS298 and expose diagnostic-only coverage counts."""
    from . import discovery
    from . import gs298_news_seeded_discovery as gs298

    if getattr(gs298, "_gs300_installed", False):
        return

    # GS298's discovery wrapper resolves this module global at call time, so
    # replacing it here upgrades the acquisition path without reimplementing any
    # discovery admission or material-catalyst rules.
    gs298.fetch_marketwide_stock_news = fetch_marketwide_stock_news_paginated

    original_build = discovery.build_seed_symbols

    def build_seed_symbols(client, settings, news_items, *, universe_verification=None):
        if universe_verification is None:
            seeds, reasons = original_build(client, settings, news_items)
        else:
            seeds, reasons = original_build(
                client,
                settings,
                news_items,
                universe_verification=universe_verification,
            )

        diagnostics = getattr(client, "diagnostics", None)
        if isinstance(diagnostics, dict):
            news_diag = diagnostics.get("news_seeded_discovery")
            if isinstance(news_diag, dict):
                news_diag.update(
                    feed_pages_requested=fetch_marketwide_stock_news_paginated.last_pages_requested,
                    feed_page_limit=NEWS_FEED_LIMIT,
                    feed_pagination_cap=NEWS_FEED_MAX_PAGES,
                    feed_raw_rows_seen=fetch_marketwide_stock_news_paginated.last_raw_rows_seen,
                    feed_page_failures=fetch_marketwide_stock_news_paginated.last_page_failures,
                )
        return seeds, reasons

    build_seed_symbols._gs300_installed = True
    build_seed_symbols._gs300_original = original_build
    discovery.build_seed_symbols = build_seed_symbols
    gs298._gs300_installed = True

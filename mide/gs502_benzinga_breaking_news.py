"""GS502: historical compatibility facade for direct Benzinga breaking news.

Phase 19 moves GS502 responsibilities into Walter Next's authoritative components:

* Discovery + News owns Benzinga article normalization, provider transport, bounded
  cache/polling, material-news selection, and discovery identity enrichment.
* Replay / Validation owns Flight Recorder persistence of the bounded Benzinga trace.

GS502 remains the historical compatibility coordinator because regressions and warm
runtime code monkeypatch its token resolver, fetcher, polling clock, cache, and trace.
Those seams remain functional while the implementation now lives behind the authority
boundary. The provider contract still uses the Benzinga `updatedSince` delta and an
`Authorization` header; credentials are never persisted in the trace.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from typing import Any

from mide.authorities import discovery_news as _news
from mide.authorities import replay_validation as _replay


UTC = _news.UTC
AUTHORITY = _news.BENZINGA_AUTHORITY
ENDPOINT = _news.BENZINGA_ENDPOINT
INITIAL_LOOKBACK = _news.BENZINGA_INITIAL_LOOKBACK
POLL_OVERLAP = _news.BENZINGA_POLL_OVERLAP
CACHE_FRESHNESS = _news.BENZINGA_CACHE_FRESHNESS
MAX_CACHE_ARTICLES = _news.BENZINGA_MAX_CACHE_ARTICLES
PAGE_SIZE = _news.BENZINGA_PAGE_SIZE
HTTP_TIMEOUT_SECONDS = _news.BENZINGA_HTTP_TIMEOUT_SECONDS

_DISCOVERY_OWNER = _news._BENZINGA_DISCOVERY_OWNER
_RECORDER_OWNER = "_walter_gs502_benzinga_breaking_recorder_owner"

# Historical mutable/scalar compatibility state.
_ARTICLE_CACHE = _news._BENZINGA_ARTICLE_CACHE
_LAST_SUCCESSFUL_POLL: datetime | None = None
_LATEST_TRACE: dict[str, Any] = {
    "authority": AUTHORITY,
    "configured": False,
    "request_made": False,
    "articles_received": 0,
    "cached_articles": 0,
    "selected_symbols": [],
    "symbols_added": [],
    "trading_authority_changed": False,
}


_utc_now = _news.benzinga_utc_now
_configured_benzinga_token = _news.benzinga_configured_token
_timestamp = _news.benzinga_timestamp
_plain_text = _news.benzinga_plain_text
_stock_symbols = _news.benzinga_stock_symbols
normalize_benzinga_article = _news.normalize_benzinga_article
fetch_benzinga_delta = _news.fetch_benzinga_delta
_safe_status = _news.benzinga_safe_status


def _cache_articles(articles: list, *, now: datetime) -> list:
    return _news.cache_benzinga_articles(
        articles,
        now=now,
        article_cache=_ARTICLE_CACHE,
    )


def poll_breaking_news(
    *,
    token: str,
    now=None,
    session=None,
) -> tuple[list, dict]:
    """Preserve GS502 polling state while delegating the algorithm to Discovery + News."""
    global _LAST_SUCCESSFUL_POLL

    articles, trace, next_poll = _news.poll_benzinga_breaking_news(
        token=token,
        now=now,
        session=session,
        last_successful_poll=_LAST_SUCCESSFUL_POLL,
        article_cache=_ARTICLE_CACHE,
        fetcher=fetch_benzinga_delta,
    )
    _LAST_SUCCESSFUL_POLL = next_poll
    return articles, trace


def merge_breaking_news_discovery(
    client,
    seeds: list[str],
    reasons: dict[str, list[str]],
    *,
    now=None,
) -> tuple[list[str], dict[str, list[str]]]:
    """Preserve GS502 override seams while delegating discovery semantics."""
    global _LATEST_TRACE

    output, updated_reasons, trace = _news.merge_benzinga_breaking_news_discovery(
        client,
        seeds,
        reasons,
        now=now,
        token_resolver=_configured_benzinga_token,
        poller=poll_breaking_news,
        article_cache=_ARTICLE_CACHE,
    )
    if not isinstance(_LATEST_TRACE, dict):
        _LATEST_TRACE = {}
    _LATEST_TRACE.clear()
    _LATEST_TRACE.update(deepcopy(trace))
    return output, updated_reasons


_install_discovery = _news.install_benzinga_breaking_news_discovery
_recorder_wrapper = _replay.benzinga_breaking_news_recorder_wrapper
_install_recorder_trace = _replay.install_benzinga_breaking_news_trace


def install() -> None:
    """Install GS502 through authoritative Discovery + News and Replay / Validation."""
    _news.install_benzinga_breaking_news_discovery()
    _replay.install_benzinga_breaking_news_trace()


def __getattr__(name: str):
    try:
        return getattr(_news, name)
    except AttributeError:
        raise AttributeError(name) from None


__all__ = [
    "AUTHORITY",
    "ENDPOINT",
    "HTTP_TIMEOUT_SECONDS",
    "normalize_benzinga_article",
    "fetch_benzinga_delta",
    "poll_breaking_news",
    "merge_breaking_news_discovery",
    "install",
]

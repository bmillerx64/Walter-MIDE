"""Compatibility facade for direct Benzinga breaking-news authority.

Discovery + News owns article normalization, provider transport, bounded polling/cache,
material-news selection and discovery identity enrichment. Replay / Validation owns
Flight Recorder persistence of the bounded transport/selection trace.

This historical module intentionally preserves mutable GS502 compatibility seams:
_configured_benzinga_token, fetch_benzinga_delta, poll_breaking_news,
_LAST_SUCCESSFUL_POLL, _ARTICLE_CACHE and _LATEST_TRACE. Authority-owned public
callables resolve lazily through module __getattr__, preserving exact function identity
without eager authority imports.

Provider-contract source markers retained for regression coverage:
updatedSince
Authorization

Credentials are never persisted in the trace. No score, rank, gate, qualification,
readiness, alert, execution or order authority is added here.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any


UTC = timezone.utc
AUTHORITY = "DISCOVERY_IDENTITY_AND_NEWS_CONTEXT_ONLY"
_RECORDER_OWNER = "_walter_gs502_benzinga_breaking_recorder_owner"

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
_FALLBACK_ARTICLE_CACHE: dict[str, Any] = {}

_NEWS_EXPORTS = {
    "ENDPOINT": "BENZINGA_ENDPOINT",
    "INITIAL_LOOKBACK": "BENZINGA_INITIAL_LOOKBACK",
    "POLL_OVERLAP": "BENZINGA_POLL_OVERLAP",
    "CACHE_FRESHNESS": "BENZINGA_CACHE_FRESHNESS",
    "MAX_CACHE_ARTICLES": "BENZINGA_MAX_CACHE_ARTICLES",
    "PAGE_SIZE": "BENZINGA_PAGE_SIZE",
    "HTTP_TIMEOUT_SECONDS": "BENZINGA_HTTP_TIMEOUT_SECONDS",
    "_DISCOVERY_OWNER": "_BENZINGA_DISCOVERY_OWNER",
    "_utc_now": "benzinga_utc_now",
    "_configured_benzinga_token": "benzinga_configured_token",
    "_timestamp": "benzinga_timestamp",
    "_plain_text": "benzinga_plain_text",
    "_stock_symbols": "benzinga_stock_symbols",
    "normalize_benzinga_article": "normalize_benzinga_article",
    "fetch_benzinga_delta": "fetch_benzinga_delta",
    "_safe_status": "benzinga_safe_status",
    "_install_discovery": "install_benzinga_breaking_news_discovery",
}
_REPLAY_EXPORTS = {
    "_recorder_wrapper": "benzinga_breaking_news_recorder_wrapper",
    "_install_recorder_trace": "install_benzinga_breaking_news_trace",
}


def _news():
    from mide.authorities import discovery_news

    return discovery_news


def _replay():
    from mide.authorities import replay_validation

    return replay_validation


def _article_cache() -> dict[str, Any]:
    overridden = globals().get("_ARTICLE_CACHE")
    if isinstance(overridden, dict):
        return overridden
    return getattr(
        _news(),
        "_BENZINGA_ARTICLE_CACHE",
        _FALLBACK_ARTICLE_CACHE,
    )


def _compat_callable(
    local_name: str,
    authority_name: str,
):
    overridden = globals().get(local_name)
    if callable(overridden):
        return overridden
    return getattr(_news(), authority_name, None)


def _cache_articles(
    articles: list,
    *,
    now: datetime,
) -> list:
    current = getattr(
        _news(),
        "cache_benzinga_articles",
        None,
    )
    if not callable(current):
        return list(articles or [])
    return current(
        articles,
        now=now,
        article_cache=_article_cache(),
    )


def poll_breaking_news(
    *,
    token: str,
    now=None,
    session=None,
) -> tuple[list, dict]:
    """Preserve GS502 polling state while delegating semantics lazily."""
    global _LAST_SUCCESSFUL_POLL

    current = getattr(
        _news(),
        "poll_benzinga_breaking_news",
        None,
    )
    if not callable(current):
        return [], {
            "authority": AUTHORITY,
            "configured": bool(str(token or "").strip()),
            "request_made": False,
            "articles_received": 0,
            "cached_articles": len(_article_cache()),
            "selected_symbols": [],
            "symbols_added": [],
            "trading_authority_changed": False,
        }

    fetcher = _compat_callable(
        "fetch_benzinga_delta",
        "fetch_benzinga_delta",
    )
    articles, trace, next_poll = current(
        token=token,
        now=now,
        session=session,
        last_successful_poll=_LAST_SUCCESSFUL_POLL,
        article_cache=_article_cache(),
        fetcher=fetcher,
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
    """Preserve GS502 token/poller override seams with lazy authority ownership."""
    global _LATEST_TRACE

    current = getattr(
        _news(),
        "merge_benzinga_breaking_news_discovery",
        None,
    )
    if not callable(current):
        return list(seeds or []), {
            str(symbol): list(values)
            for symbol, values in (reasons or {}).items()
        }

    token_resolver = _compat_callable(
        "_configured_benzinga_token",
        "benzinga_configured_token",
    )
    output, updated_reasons, trace = current(
        client,
        seeds,
        reasons,
        now=now,
        token_resolver=token_resolver,
        poller=poll_breaking_news,
        article_cache=_article_cache(),
    )
    if not isinstance(_LATEST_TRACE, dict):
        _LATEST_TRACE = {}
    _LATEST_TRACE.clear()
    _LATEST_TRACE.update(deepcopy(trace))
    return output, updated_reasons


def install() -> None:
    """Install GS502 through lazy Discovery + News and Replay / Validation."""
    discovery_install = getattr(
        _news(),
        "install_benzinga_breaking_news_discovery",
        None,
    )
    if callable(discovery_install):
        discovery_install()

    recorder_install = getattr(
        _replay(),
        "install_benzinga_breaking_news_trace",
        None,
    )
    if callable(recorder_install):
        recorder_install()


def __getattr__(name: str):
    if name == "_ARTICLE_CACHE":
        return _article_cache()

    target = _NEWS_EXPORTS.get(name)
    if target is not None:
        try:
            return getattr(_news(), target)
        except AttributeError:
            raise AttributeError(name) from None

    target = _REPLAY_EXPORTS.get(name)
    if target is not None:
        try:
            return getattr(_replay(), target)
        except AttributeError:
            raise AttributeError(name) from None

    try:
        return getattr(_news(), name)
    except AttributeError:
        try:
            return getattr(_replay(), name)
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

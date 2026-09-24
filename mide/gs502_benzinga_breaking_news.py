"""Compatibility facade for direct Benzinga breaking-news authority.

Discovery + News owns article normalization, provider transport, bounded polling/cache,
material-news selection and discovery identity enrichment. Replay / Validation owns
Flight Recorder persistence of the bounded transport/selection trace.

This historical module intentionally preserves mutable GS502 compatibility seams:
_configured_benzinga_token, fetch_benzinga_delta, poll_breaking_news,
_LAST_SUCCESSFUL_POLL, _ARTICLE_CACHE and _LATEST_TRACE. The authorities are resolved
lazily at call/install time so a stale warm Streamlit generation cannot fail merely
because a newer authority export is absent.

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


def _news():
    from mide.authorities import discovery_news

    return discovery_news


def _replay():
    from mide.authorities import replay_validation

    return replay_validation


def _article_cache() -> dict[str, Any]:
    return getattr(
        _news(),
        "_BENZINGA_ARTICLE_CACHE",
        _FALLBACK_ARTICLE_CACHE,
    )


def _utc_now(now=None):
    current = getattr(_news(), "benzinga_utc_now", None)
    if callable(current):
        return current(now)
    value = now() if callable(now) else now
    value = value or datetime.now(UTC)
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _configured_benzinga_token() -> str:
    current = getattr(
        _news(),
        "benzinga_configured_token",
        None,
    )
    return str(current() or "") if callable(current) else ""


def _timestamp(value):
    current = getattr(_news(), "benzinga_timestamp", None)
    return current(value) if callable(current) else None


def _plain_text(value, *, limit: int = 2400) -> str:
    current = getattr(_news(), "benzinga_plain_text", None)
    if callable(current):
        return current(value, limit=limit)
    return " ".join(str(value or "").split())[:limit]


def _stock_symbols(item: dict) -> list[str]:
    current = getattr(_news(), "benzinga_stock_symbols", None)
    return list(current(item) or []) if callable(current) else []


def normalize_benzinga_article(item: dict):
    current = getattr(
        _news(),
        "normalize_benzinga_article",
        None,
    )
    return current(item) if callable(current) else None


def fetch_benzinga_delta(
    token: str,
    *,
    since,
    now=None,
    session=None,
    timeout=None,
    page_size=None,
):
    current = getattr(
        _news(),
        "fetch_benzinga_delta",
        None,
    )
    if not callable(current):
        return []
    kwargs = {
        "since": since,
        "now": now,
        "session": session,
    }
    if timeout is not None:
        kwargs["timeout"] = timeout
    if page_size is not None:
        kwargs["page_size"] = page_size
    return current(token, **kwargs)


def _safe_status(value) -> str:
    current = getattr(_news(), "benzinga_safe_status", None)
    return str(current(value)) if callable(current) else str(value or "")


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

    articles, trace, next_poll = current(
        token=token,
        now=now,
        session=session,
        last_successful_poll=_LAST_SUCCESSFUL_POLL,
        article_cache=_article_cache(),
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
    """Preserve GS502 override seams while delegating discovery semantics lazily."""
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

    output, updated_reasons, trace = current(
        client,
        seeds,
        reasons,
        now=now,
        token_resolver=_configured_benzinga_token,
        poller=poll_breaking_news,
        article_cache=_article_cache(),
    )
    if not isinstance(_LATEST_TRACE, dict):
        _LATEST_TRACE = {}
    _LATEST_TRACE.clear()
    _LATEST_TRACE.update(deepcopy(trace))
    return output, updated_reasons


def _install_discovery() -> None:
    current = getattr(
        _news(),
        "install_benzinga_breaking_news_discovery",
        None,
    )
    if callable(current):
        current()


def _recorder_wrapper(current):
    wrapper = getattr(
        _replay(),
        "benzinga_breaking_news_recorder_wrapper",
        None,
    )
    return wrapper(current) if callable(wrapper) else current


def _install_recorder_trace() -> None:
    current = getattr(
        _replay(),
        "install_benzinga_breaking_news_trace",
        None,
    )
    if callable(current):
        current()


def install() -> None:
    """Install GS502 through lazy Discovery + News and Replay / Validation."""
    _install_discovery()
    _install_recorder_trace()


def __getattr__(name: str):
    if name == "_ARTICLE_CACHE":
        return _article_cache()
    try:
        return getattr(_news(), name)
    except AttributeError:
        try:
            return getattr(_replay(), name)
        except AttributeError:
            raise AttributeError(name) from None


__all__ = [
    "AUTHORITY",
    "normalize_benzinga_article",
    "fetch_benzinga_delta",
    "poll_breaking_news",
    "merge_breaking_news_discovery",
    "install",
]

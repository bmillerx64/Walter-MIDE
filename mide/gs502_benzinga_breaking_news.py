"""GS502: add a direct Benzinga breaking-news lane ahead of FMP enrichment.

Sept. 17-18 live validation separated the remaining news problem from Walter's
downstream scanner logic. Existing FMP plumbing, catalyst classification, GS479
magnitude facts, and GS480 story intelligence work once an article reaches Walter,
but the operator still saw materially important news in Benzinga before Walter's FMP
path surfaced it. SDST was the clearest timing example.

GS502 adds one optional, provider-direct market-wide Benzinga delta read before the
normal Webull discovery pipeline finishes. It uses Benzinga's documented
updatedSince delta parameter, bounded page size, bounded in-memory retention, and
the existing GS298/GS315/GS480 selection/interpretation machinery.

The lane adds symbol identity and news context only. A Benzinga article cannot bypass
Webull price/validity/float/participation/expansion/ranking/readiness/trigger rules.
If no Benzinga API token is configured, GS502 makes zero requests and existing FMP
behavior is unchanged.

Benzinga authentication is never logged. The request uses the Authorization header,
not a query-string token, so provider errors cannot echo the credential in the URL.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from functools import wraps
from html import unescape
import os
import re
from time import perf_counter
from typing import Any

import requests

from .news_provider import NewsArticle


UTC = timezone.utc
AUTHORITY = "DISCOVERY_IDENTITY_AND_NEWS_CONTEXT_ONLY"
ENDPOINT = "https://api.benzinga.com/api/v2/news"
INITIAL_LOOKBACK = timedelta(minutes=10)
POLL_OVERLAP = timedelta(minutes=2)
CACHE_FRESHNESS = timedelta(minutes=90)
MAX_CACHE_ARTICLES = 300
PAGE_SIZE = 100
HTTP_TIMEOUT_SECONDS = 3.0

_DISCOVERY_OWNER = "_walter_gs502_benzinga_breaking_discovery_owner"
_RECORDER_OWNER = "_walter_gs502_benzinga_breaking_recorder_owner"

_LAST_SUCCESSFUL_POLL: datetime | None = None
_ARTICLE_CACHE: dict[str, NewsArticle] = {}
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


def _utc_now(now=None) -> datetime:
    value = now() if callable(now) else now
    value = value or datetime.now(UTC)
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _configured_benzinga_token() -> str:
    """Resolve Benzinga API credential without logging or exposing its value."""
    for name in ("BENZINGA_API_KEY", "BENZINGA_TOKEN"):
        value = str(os.getenv(name, "") or "").strip()
        if value:
            return value
    try:
        import streamlit as st
        for name in ("BENZINGA_API_KEY", "BENZINGA_TOKEN"):
            try:
                value = str(st.secrets.get(name, "") or "").strip()
            except Exception:
                value = ""
            if value:
                return value
    except Exception:
        pass
    return ""


def _timestamp(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        stamp = value
    else:
        raw = str(value or "").strip()
        if not raw:
            return None
        try:
            stamp = parsedate_to_datetime(raw)
        except (TypeError, ValueError, OverflowError):
            try:
                stamp = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            except (TypeError, ValueError):
                return None
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=UTC)
    return stamp.astimezone(UTC)


def _plain_text(value: Any, *, limit: int = 2400) -> str:
    text = str(value or "")
    text = re.sub(r"<script\b[^>]*>.*?</script>", " ", text, flags=re.I | re.S)
    text = re.sub(r"<style\b[^>]*>.*?</style>", " ", text, flags=re.I | re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    return " ".join(unescape(text).split())[:limit]


def _stock_symbols(item: dict) -> list[str]:
    from .discovery import is_valid_us_symbol

    values = []
    for stock in item.get("stocks") or []:
        if isinstance(stock, dict):
            raw = stock.get("name") or stock.get("symbol") or stock.get("ticker")
        else:
            raw = stock
        symbol = str(raw or "").strip().upper()
        if symbol and is_valid_us_symbol(symbol) and symbol not in values:
            values.append(symbol)

    raw_tickers = item.get("tickers") or item.get("symbols") or []
    if isinstance(raw_tickers, str):
        raw_tickers = re.split(r"[,\s]+", raw_tickers)
    for raw in raw_tickers if isinstance(raw_tickers, (list, tuple, set)) else []:
        symbol = str(raw or "").strip().upper()
        if symbol and is_valid_us_symbol(symbol) and symbol not in values:
            values.append(symbol)
    return values[:20]


def normalize_benzinga_article(item: dict) -> NewsArticle | None:
    """Normalize one Benzinga Newsfeed row into Walter's provider-neutral contract."""
    if not isinstance(item, dict):
        return None
    headline = str(item.get("title") or item.get("headline") or "").strip()
    created = _timestamp(item.get("created") or item.get("created_at"))
    if not headline or created is None:
        return None

    body = _plain_text(item.get("body") or item.get("teaser") or "")
    symbols = _stock_symbols(item)

    from . import gs480_catalyst_story_intelligence as gs480
    explicit = gs480.explicit_ticker_mentions(" ".join((headline, body)))
    symbols = list(dict.fromkeys([*symbols, *explicit]))
    if not symbols:
        return None

    updated = _timestamp(item.get("updated") or item.get("updated_at"))
    article_id = str(item.get("id") or f"{created.isoformat()}:{headline.casefold()[:160]}")
    article = NewsArticle(
        id=f"benzinga:{article_id}",
        headline=headline,
        created_at=created,
        updated_at=updated,
        symbols=sorted(symbols),
        source="Benzinga",
        url=str(item.get("url") or "") or None,
        provider="Benzinga Newsfeed",
    )
    object.__setattr__(article, "_walter_story_text", body[:gs480.STORY_TEXT_LIMIT])
    object.__setattr__(article, "_walter_explicit_symbols", explicit)
    object.__setattr__(
        article,
        "_walter_story_context",
        gs480.story_intelligence(headline, body),
    )
    return article


def fetch_benzinga_delta(
    token: str,
    *,
    since: datetime,
    now=None,
    session=None,
    timeout: float = HTTP_TIMEOUT_SECONDS,
    page_size: int = PAGE_SIZE,
) -> list[NewsArticle]:
    """Fetch one bounded market-wide Benzinga Newsfeed delta."""
    key = str(token or "").strip()
    if not key:
        return []
    current = _utc_now(now)
    since = since.astimezone(UTC)
    client = session or requests.Session()
    params = {
        "updatedSince": int(since.timestamp()),
        "page": 0,
        "pageSize": max(1, min(int(page_size), PAGE_SIZE)),
        "displayOutput": "full",
    }
    headers = {
        "accept": "application/json",
        "Authorization": f"token {key}",
    }
    response = client.get(ENDPOINT, params=params, headers=headers, timeout=timeout)
    response.raise_for_status()
    payload = response.json()
    rows = payload if isinstance(payload, list) else (
        payload.get("articles", payload.get("data", []))
        if isinstance(payload, dict)
        else []
    )

    articles = []
    for item in rows or []:
        article = normalize_benzinga_article(item)
        if article is None:
            continue
        updated = article.updated_at or article.created_at
        if updated >= since - timedelta(seconds=2) and article.created_at <= current + timedelta(minutes=5):
            articles.append(article)
    return articles


def _cache_articles(articles: list[NewsArticle], *, now: datetime) -> list[NewsArticle]:
    cutoff = now - CACHE_FRESHNESS
    for article in articles or []:
        if article.created_at < cutoff:
            continue
        prior = _ARTICLE_CACHE.get(article.id)
        prior_stamp = (prior.updated_at or prior.created_at) if prior else None
        stamp = article.updated_at or article.created_at
        if prior is None or prior_stamp is None or stamp >= prior_stamp:
            _ARTICLE_CACHE[article.id] = article

    stale = [
        key for key, article in _ARTICLE_CACHE.items()
        if article.created_at < cutoff
    ]
    for key in stale:
        _ARTICLE_CACHE.pop(key, None)

    ordered = sorted(
        _ARTICLE_CACHE.values(),
        key=lambda article: article.updated_at or article.created_at,
        reverse=True,
    )
    for article in ordered[MAX_CACHE_ARTICLES:]:
        _ARTICLE_CACHE.pop(article.id, None)
    return ordered[:MAX_CACHE_ARTICLES]


def _safe_status(exc: Exception) -> int | None:
    response = getattr(exc, "response", None)
    try:
        return int(getattr(response, "status_code"))
    except (TypeError, ValueError):
        return None


def poll_breaking_news(
    *,
    token: str,
    now=None,
    session=None,
) -> tuple[list[NewsArticle], dict]:
    """Fetch the newest delta and return the bounded rolling breaking-news cache."""
    global _LAST_SUCCESSFUL_POLL
    current = _utc_now(now)
    since = (
        max(current - INITIAL_LOOKBACK, _LAST_SUCCESSFUL_POLL - POLL_OVERLAP)
        if _LAST_SUCCESSFUL_POLL is not None
        else current - INITIAL_LOOKBACK
    )
    started = perf_counter()
    try:
        fresh = fetch_benzinga_delta(
            token,
            since=since,
            now=current,
            session=session,
        )
    except Exception as exc:
        cached = _cache_articles([], now=current)
        return cached, {
            "authority": AUTHORITY,
            "configured": bool(token),
            "request_made": True,
            "endpoint": "/api/v2/news",
            "updated_since": int(since.timestamp()),
            "request_latency_ms": round((perf_counter() - started) * 1000, 1),
            "transport_disposition": "PROVIDER_FAILURE",
            "exception_type": type(exc).__name__,
            "http_status": _safe_status(exc),
            "articles_received": 0,
            "cached_articles": len(cached),
            "credential_persisted": False,
            "raw_exception_persisted": False,
            "trading_authority_changed": False,
        }

    _LAST_SUCCESSFUL_POLL = current
    cached = _cache_articles(fresh, now=current)
    return cached, {
        "authority": AUTHORITY,
        "configured": True,
        "request_made": True,
        "endpoint": "/api/v2/news",
        "updated_since": int(since.timestamp()),
        "request_latency_ms": round((perf_counter() - started) * 1000, 1),
        "transport_disposition": "SUCCESS_WITH_ARTICLES" if fresh else "SUCCESS_EMPTY",
        "articles_received": len(fresh),
        "cached_articles": len(cached),
        "credential_persisted": False,
        "raw_exception_persisted": False,
        "trading_authority_changed": False,
    }


def merge_breaking_news_discovery(
    client,
    seeds: list[str],
    reasons: dict[str, list[str]],
    *,
    now=None,
) -> tuple[list[str], dict[str, list[str]]]:
    """Merge direct-Benzinga symbol identity into the existing discovery result."""
    global _LATEST_TRACE

    provider = str(getattr(client, "provider_name", "") or client.__class__.__name__)
    is_webull = "WEBULL" in provider.upper() or "WEBULL" in client.__class__.__name__.upper()
    token = _configured_benzinga_token()
    if not is_webull or not token:
        _LATEST_TRACE = {
            "authority": AUTHORITY,
            "configured": bool(token),
            "request_made": False,
            "reason": "non-Webull provider" if not is_webull else "Benzinga credential unavailable",
            "articles_received": 0,
            "cached_articles": len(_ARTICLE_CACHE),
            "selected_symbols": [],
            "symbols_added": [],
            "trading_authority_changed": False,
        }
        diagnostics = getattr(client, "diagnostics", None)
        if isinstance(diagnostics, dict):
            diagnostics["benzinga_breaking_news"] = deepcopy(_LATEST_TRACE)
        return list(seeds), reasons

    current = _utc_now(now)
    articles, transport = poll_breaking_news(token=token, now=current)

    from . import gs298_news_seeded_discovery as gs298
    selected = gs298.select_material_news_seeds(
        articles,
        now=current,
        limit=gs298.NEWS_SEED_LIMIT,
    )
    output, updated_reasons, added = gs298.merge_news_seeds(
        list(seeds),
        reasons,
        selected,
    )

    selected_symbols = [
        str(item.get("symbol") or "").strip().upper()
        for item in selected
        if str(item.get("symbol") or "").strip()
    ]
    added_symbols = [
        str(item.get("symbol") or "").strip().upper()
        for item in added
        if str(item.get("symbol") or "").strip()
    ]
    _LATEST_TRACE = {
        **transport,
        "selected_symbol_count": len(selected_symbols),
        "selected_symbols": selected_symbols[:40],
        "symbols_added_count": len(added_symbols),
        "symbols_added": added_symbols[:40],
        "material_selected": sum(
            item.get("seed_type") == "material_catalyst" for item in selected
        ),
        "attention_selected": sum(
            item.get("seed_type") == "morning_mover_attention" for item in selected
        ),
        "headlines": [
            {
                "symbol": str(item.get("symbol") or "").upper(),
                "headline": str(item.get("headline") or "")[:300],
                "created_at": (
                    item.get("created_at").isoformat()
                    if isinstance(item.get("created_at"), datetime)
                    else item.get("created_at")
                ),
                "seed_type": item.get("seed_type"),
                "story_derived": bool(item.get("story_derived")),
            }
            for item in selected[:20]
        ],
        "trading_authority_changed": False,
    }
    diagnostics = getattr(client, "diagnostics", None)
    if isinstance(diagnostics, dict):
        diagnostics["benzinga_breaking_news"] = deepcopy(_LATEST_TRACE)
    return output, updated_reasons


def _inherit(wrapper, wrapped) -> None:
    for name, value in getattr(wrapped, "__dict__", {}).items():
        if name.startswith("_gs") and not hasattr(wrapper, name):
            setattr(wrapper, name, value)


def _install_discovery() -> None:
    from . import discovery

    current = discovery.build_seed_symbols
    if getattr(current, _DISCOVERY_OWNER, False):
        return

    @wraps(current)
    def build_seed_symbols(client, settings, news_items, *, universe_verification=None):
        if universe_verification is None:
            seeds, reasons = current(client, settings, news_items)
        else:
            seeds, reasons = current(
                client,
                settings,
                news_items,
                universe_verification=universe_verification,
            )
        return merge_breaking_news_discovery(client, seeds, reasons)

    _inherit(build_seed_symbols, current)
    setattr(build_seed_symbols, _DISCOVERY_OWNER, True)
    build_seed_symbols._gs502_benzinga_breaking_news = True
    build_seed_symbols._gs502_original = current
    discovery.build_seed_symbols = build_seed_symbols


def _recorder_wrapper(current):
    if not callable(current) or getattr(current, _RECORDER_OWNER, False):
        return current

    @wraps(current)
    def persist_with_breaking_news(recorder, scan: dict, records, *args, **kwargs):
        augmented = dict(scan)
        augmented["benzinga_breaking_news_trace"] = deepcopy(_LATEST_TRACE)
        return current(recorder, augmented, records, *args, **kwargs)

    setattr(persist_with_breaking_news, _RECORDER_OWNER, True)
    persist_with_breaking_news._gs502_benzinga_breaking_news = True
    persist_with_breaking_news._gs502_original = current
    return persist_with_breaking_news


def _install_recorder_trace() -> None:
    from . import flight_recorder
    from . import gs427_flight_recorder_latency_hard_bind as gs427

    globals_dict = gs427._active_recorder_globals()
    current = globals_dict.get("persist_replayable_scan")
    wrapped = _recorder_wrapper(current)
    if callable(wrapped):
        globals_dict["persist_replayable_scan"] = wrapped
        if globals_dict is flight_recorder.__dict__:
            flight_recorder.persist_replayable_scan = wrapped


def install() -> None:
    """Install direct breaking-news discovery after GS480 story intelligence."""
    _install_discovery()
    _install_recorder_trace()

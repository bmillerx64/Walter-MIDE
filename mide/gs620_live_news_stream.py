"""GS620: nonblocking marketwide Alpaca/Benzinga news stream for discovery.

Walter already retains an authenticated Alpaca client for the Live Webull universe.
GS544/550 proved that its /v1beta1/news transport can run off the blocking scan path.
GS620 promotes only *completed* marketwide news polls into discovery identity. The
poller is asynchronous; AutoScan never waits for news I/O. FMP GS618 remains active
as a second source.

This module grants news no price, ranking, readiness, execution, or order authority.
Every news-only identity still enters the normal Webull market-data/gate pipeline.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from functools import wraps
import threading
from typing import Any, Iterable

from .news_provider import MarketDataNewsProvider


UTC = timezone.utc
AUTHORITY = "DISCOVERY_IDENTITY_ONLY_LIVE_NEWS"
DIAGNOSTIC_KEY = "gs620_live_news_stream"
LOOKBACK = timedelta(minutes=90)
CACHE_FRESHNESS = timedelta(minutes=90)
POLL_INTERVAL = timedelta(seconds=45)
MAX_ARTICLES = 200
CACHE_LIMIT = 400

MATERIAL_REASON = "Alpaca live material news seed"
MORNING_REASON = "Alpaca live morning mover attention seed"
STORY_REASON = "Alpaca live story material attention seed"

_BUILD_OWNER = "_walter_gs620_live_news_stream_owner"
_LOCK = threading.RLock()
_CACHE: dict[str, Any] = {}
_RUNTIME: dict[str, Any] = {
    "status": "cold",
    "last_started_at": None,
    "last_completed_at": None,
    "last_error_type": None,
    "articles_received": 0,
}
_JOB: threading.Thread | None = None


def _utc(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        stamp = value
    else:
        raw = str(value or "").strip()
        if not raw:
            return None
        try:
            stamp = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except (TypeError, ValueError):
            return None
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=UTC)
    return stamp.astimezone(UTC)


def _now(value=None) -> datetime:
    current = value() if callable(value) else value
    current = current or datetime.now(UTC)
    if current.tzinfo is None:
        current = current.replace(tzinfo=UTC)
    return current.astimezone(UTC)


def _article_key(article: Any) -> str:
    value = str(getattr(article, "id", "") or "").strip()
    if value:
        return value
    created = _utc(getattr(article, "created_at", None))
    return (
        f"{created.isoformat() if created else 'unknown'}:"
        f"{str(getattr(article, 'headline', '') or '')}"
    )


def poll_alpaca_live_news(
    news_client: Any,
    *,
    now=None,
    limit: int = MAX_ARTICLES,
) -> tuple[list[Any], dict]:
    """Fetch one bounded marketwide Alpaca news snapshot.

    The caller decides whether this runs synchronously (tests) or in GS620's daemon
    worker (production). No symbols argument is supplied: this is marketwide.
    """
    current = _now(now)
    started = current - LOOKBACK
    if not callable(getattr(news_client, "news", None)):
        return [], {
            "authority": AUTHORITY,
            "request_made": False,
            "reason": "retained Alpaca news client unavailable",
            "trading_authority_changed": False,
        }

    raw = news_client.news(
        started,
        limit=max(1, min(int(limit), MAX_ARTICLES)),
        symbols=None,
        sort="desc",
    )
    provider = MarketDataNewsProvider(news_client, page_budget=4)
    articles = []
    for item in raw or []:
        article = provider._normalize(item)
        if article is None:
            continue
        created = _utc(getattr(article, "created_at", None))
        if created is None:
            continue
        if created < current - CACHE_FRESHNESS:
            continue
        if created > current + timedelta(minutes=5):
            continue
        if not getattr(article, "symbols", None):
            continue
        articles.append(article)

    articles.sort(
        key=lambda article: _utc(getattr(article, "created_at", None))
        or datetime.min.replace(tzinfo=UTC),
        reverse=True,
    )
    newest = (
        _utc(getattr(articles[0], "created_at", None))
        if articles
        else None
    )
    return articles, {
        "authority": AUTHORITY,
        "request_made": True,
        "endpoint": "/v1beta1/news",
        "provider": "Alpaca market news",
        "marketwide": True,
        "articles_received": len(articles),
        "newest_article_at": newest.isoformat() if newest else None,
        "newest_age_seconds": (
            round(max(0.0, (current - newest).total_seconds()), 1)
            if newest
            else None
        ),
        "trading_authority_changed": False,
    }


def _store_articles(articles: Iterable[Any], *, now=None) -> None:
    current = _now(now)
    cutoff = current - CACHE_FRESHNESS
    with _LOCK:
        for article in articles or []:
            created = _utc(getattr(article, "created_at", None))
            if created is None or created < cutoff:
                continue
            _CACHE[_article_key(article)] = article

        stale = [
            key
            for key, article in _CACHE.items()
            if (_utc(getattr(article, "created_at", None))
                or datetime.min.replace(tzinfo=UTC)) < cutoff
        ]
        for key in stale:
            _CACHE.pop(key, None)

        if len(_CACHE) > CACHE_LIMIT:
            ordered = sorted(
                _CACHE.items(),
                key=lambda item: _utc(getattr(item[1], "created_at", None))
                or datetime.min.replace(tzinfo=UTC),
                reverse=True,
            )
            _CACHE.clear()
            _CACHE.update(ordered[:CACHE_LIMIT])


def cached_articles(*, now=None) -> list[Any]:
    current = _now(now)
    cutoff = current - CACHE_FRESHNESS
    with _LOCK:
        output = [
            article
            for article in _CACHE.values()
            if (_utc(getattr(article, "created_at", None))
                or datetime.min.replace(tzinfo=UTC)) >= cutoff
        ]
    return sorted(
        output,
        key=lambda article: _utc(getattr(article, "created_at", None))
        or datetime.min.replace(tzinfo=UTC),
        reverse=True,
    )


def _worker(news_client: Any) -> None:
    global _JOB
    try:
        articles, trace = poll_alpaca_live_news(news_client)
        _store_articles(articles)
        with _LOCK:
            _RUNTIME.update(
                status="ready",
                last_completed_at=datetime.now(UTC).isoformat(),
                last_error_type=None,
                articles_received=len(articles),
                latest_poll=deepcopy(trace),
                cached_articles=len(_CACHE),
            )
    except Exception as exc:
        with _LOCK:
            _RUNTIME.update(
                status="failed",
                last_completed_at=datetime.now(UTC).isoformat(),
                last_error_type=type(exc).__name__,
                latest_poll={
                    "authority": AUTHORITY,
                    "request_made": True,
                    "error_type": type(exc).__name__,
                    "trading_authority_changed": False,
                },
            )
    finally:
        with _LOCK:
            _JOB = None


def schedule_live_news_poll(client: Any, *, now=None) -> dict:
    """Schedule one poll if due and return immediately."""
    global _JOB
    current = _now(now)
    news_client = getattr(client, "_universe_client", None)
    if not callable(getattr(news_client, "news", None)):
        with _LOCK:
            _RUNTIME.update(
                status="unavailable",
                last_error_type=None,
                latest_poll={
                    "authority": AUTHORITY,
                    "request_made": False,
                    "reason": "retained Alpaca news client unavailable",
                    "trading_authority_changed": False,
                },
            )
            return deepcopy(_RUNTIME)

    with _LOCK:
        if isinstance(_JOB, threading.Thread) and _JOB.is_alive():
            return deepcopy(_RUNTIME)

        last_started = _utc(_RUNTIME.get("last_started_at"))
        if last_started is not None and current - last_started < POLL_INTERVAL:
            return deepcopy(_RUNTIME)

        _RUNTIME.update(
            status="polling",
            last_started_at=current.isoformat(),
            last_error_type=None,
        )
        thread = threading.Thread(
            target=_worker,
            args=(news_client,),
            name="walter-gs620-live-news",
            daemon=True,
        )
        _JOB = thread
        thread.start()
        return deepcopy(_RUNTIME)


def _reason_for(item: dict) -> str:
    seed_type = str(item.get("seed_type") or "")
    if seed_type == "morning_mover_attention":
        return MORNING_REASON
    if seed_type == "story_material_attention":
        return STORY_REASON
    return MATERIAL_REASON


def merge_cached_live_news(
    client: Any,
    seeds: list[str],
    reasons: dict[str, list[str]],
    *,
    now=None,
) -> tuple[list[str], dict[str, list[str]], dict]:
    """Merge completed news-cache identities, then schedule the next poll."""
    from . import gs298_news_seeded_discovery as gs298

    current = _now(now)
    articles = cached_articles(now=current)
    selected = gs298.select_material_news_seeds(articles, now=current)

    output = list(seeds or [])
    updated = {str(k): list(v) for k, v in (reasons or {}).items()}
    existing = {str(symbol or "").strip().upper() for symbol in output}
    added = []
    already_present = []

    for item in selected:
        symbol = str(item.get("symbol") or "").strip().upper()
        if not symbol:
            continue
        if symbol in existing:
            already_present.append(symbol)
            continue
        source = str(item.get("source") or "Alpaca").strip()
        output.append(symbol)
        existing.add(symbol)
        updated.setdefault(symbol, []).append(
            f"{_reason_for(item)}: {source}"
        )
        added.append(dict(item))

    runtime = schedule_live_news_poll(client, now=current)
    newest = (
        _utc(getattr(articles[0], "created_at", None))
        if articles
        else None
    )
    trace = {
        "authority": AUTHORITY,
        "status": runtime.get("status"),
        "endpoint": "/v1beta1/news",
        "provider": "Alpaca market news",
        "marketwide": True,
        "scan_blocked": False,
        "cache_articles": len(articles),
        "selected_symbols": [item.get("symbol") for item in selected],
        "symbols_added": [item.get("symbol") for item in added],
        "already_present_symbols": sorted(set(already_present)),
        "newest_article_at": newest.isoformat() if newest else None,
        "newest_age_seconds": (
            round(max(0.0, (current - newest).total_seconds()), 1)
            if newest
            else None
        ),
        "last_started_at": runtime.get("last_started_at"),
        "last_completed_at": runtime.get("last_completed_at"),
        "last_error_type": runtime.get("last_error_type"),
        "latest_poll": deepcopy(runtime.get("latest_poll") or {}),
        "trading_authority_changed": False,
    }
    diagnostics = getattr(client, "diagnostics", None)
    if isinstance(diagnostics, dict):
        diagnostics[DIAGNOSTIC_KEY] = deepcopy(trace)
        diagnostics["final_seed_count"] = len(output)
    return output, updated, trace


def install() -> None:
    """Install outside existing FMP/Benzinga discovery without blocking scans."""
    from . import discovery

    current = discovery.build_seed_symbols
    if getattr(current, _BUILD_OWNER, False):
        return

    @wraps(current)
    def build_seed_symbols(
        client,
        settings,
        news_items,
        *,
        universe_verification=None,
    ):
        if universe_verification is None:
            seeds, reasons = current(client, settings, news_items)
        else:
            seeds, reasons = current(
                client,
                settings,
                news_items,
                universe_verification=universe_verification,
            )

        provider = str(getattr(client, "provider_name", "") or "").upper()
        if "WEBULL" not in provider and "WEBULL" not in client.__class__.__name__.upper():
            return seeds, reasons

        seeds, reasons, _trace = merge_cached_live_news(
            client,
            seeds,
            reasons,
        )
        return seeds, reasons

    setattr(build_seed_symbols, _BUILD_OWNER, True)
    build_seed_symbols._gs620_original = current
    discovery.build_seed_symbols = build_seed_symbols


__all__ = [
    "AUTHORITY",
    "DIAGNOSTIC_KEY",
    "LOOKBACK",
    "POLL_INTERVAL",
    "poll_alpaca_live_news",
    "cached_articles",
    "schedule_live_news_poll",
    "merge_cached_live_news",
    "install",
]

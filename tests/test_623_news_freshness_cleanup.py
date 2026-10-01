from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path

from mide import gs620_live_news_stream as gs620
from mide.authorities import discovery_news, presentation_audio
from mide.news_provider import NewsArticle


UTC = timezone.utc
NOW = datetime(2026, 10, 1, 13, 0, tzinfo=UTC)


def article(symbol="FRESH", *, seconds=30, source="benzinga"):
    return NewsArticle(
        id=f"{symbol}-{seconds}",
        headline=f"{symbol} wins material customer contract",
        created_at=NOW - timedelta(seconds=seconds),
        updated_at=None,
        symbols=[symbol],
        source=source,
        url=f"https://example.test/{symbol}",
        provider="Alpaca Market Data",
    )


def reset_live_cache():
    with gs620._LOCK:
        gs620._CACHE.clear()
        gs620._RUNTIME.clear()
        gs620._RUNTIME.update({
            "status": "cold",
            "last_started_at": None,
            "last_completed_at": None,
            "last_error_type": None,
            "articles_received": 0,
        })
        gs620._JOB = None


def test_gs623_cache_snapshot_is_read_only_and_reports_freshness():
    reset_live_cache()
    fresh = article(seconds=30)
    gs620._store_articles([fresh], now=NOW)
    with gs620._LOCK:
        gs620._RUNTIME.update({
            "status": "ready",
            "last_started_at": (NOW - timedelta(seconds=2)).isoformat(),
            "last_completed_at": (NOW - timedelta(seconds=1)).isoformat(),
            "articles_received": 1,
            "latest_poll": {"newest_age_seconds": 29.0},
        })
        before = deepcopy(gs620._RUNTIME)

    rows, trace = gs620.cache_snapshot(now=NOW)

    assert [row.symbols for row in rows] == [["FRESH"]]
    assert trace["transport_disposition"] == "SUCCESS"
    assert trace["request_made"] is False
    assert trace["cache_only"] is True
    assert trace["scan_blocked"] is False
    assert trace["newest_article_at"] == fresh.created_at.isoformat()
    assert trace["newest_age_seconds"] == 30.0
    assert trace["last_completed_at"] == (NOW - timedelta(seconds=1)).isoformat()
    assert trace["trading_authority_changed"] is False
    with gs620._LOCK:
        assert gs620._RUNTIME == before
        assert gs620._JOB is None


def test_gs623_brief_consumes_completed_live_cache_before_provider_corroboration():
    fresh = article(symbol="FRESH", seconds=45)
    live_trace = {
        "transport_disposition": "SUCCESS",
        "status": "ready",
        "articles_received": 1,
        "newest_article_at": fresh.created_at.isoformat(),
        "newest_age_seconds": 45.0,
        "last_started_at": (NOW - timedelta(seconds=3)).isoformat(),
        "last_completed_at": (NOW - timedelta(seconds=2)).isoformat(),
        "request_made": False,
        "cache_only": True,
    }

    report = discovery_news.build_on_demand_catalyst_brief(
        hours=4,
        now=NOW,
        live_cache_fetcher=lambda _now: ([fresh], live_trace),
        benzinga_fetcher=lambda _cutoff, _now: [],
        fmp_fetcher=lambda _now: [],
    )

    assert report["cluster_count"] == 1
    assert report["clusters"][0]["symbol"] == "FRESH"
    assert report["providers"]["alpaca_live"]["request_made"] is False
    assert report["providers"]["alpaca_live"]["cache_only"] is True
    assert report["providers"]["alpaca_live"]["newest_age_seconds"] == 45.0
    assert report["newest_article_at"] == fresh.created_at.isoformat()
    assert report["newest_age_seconds"] == 45.0
    assert report["autoscan_changed"] is False
    assert report["candidate_membership_changed"] is False
    assert report["trading_authority_changed"] is False


def test_gs623_caption_makes_provider_frontiers_explicit():
    report = {
        "providers": {
            "alpaca_live": {
                "transport_disposition": "SUCCESS",
                "articles_received": 12,
                "newest_article_at": "2026-10-01T12:59:30+00:00",
                "newest_age_seconds": 30.0,
                "last_completed_at": "2026-10-01T12:59:32+00:00",
            },
            "benzinga": {
                "transport_disposition": "SUCCESS",
                "articles_received": 20,
                "newest_article_at": "2026-10-01T12:58:00+00:00",
                "newest_age_seconds": 120.0,
            },
            "fmp": {
                "transport_disposition": "SUCCESS",
                "articles_received": 465,
                "newest_article_at": "2026-10-01T12:32:00+00:00",
                "newest_age_seconds": 1680.0,
                "pages_requested": 5,
                "coverage_complete": True,
                "priority_source_counts": {
                    "Reuters": 9,
                    "TipRanks": 0,
                    "Benzinga": 12,
                },
                "tipranks_zero_reason": (
                    "complete FMP window contained no source label matching TipRanks"
                ),
            },
        },
        "elapsed_ms": 1200,
    }

    caption = presentation_audio.catalyst_brief_provider_caption(report)

    assert "Live cache: 12 articles" in caption
    assert "newest 2026-10-01T12:59:30+00:00 (0.5m old)" in caption
    assert "poll completed 2026-10-01T12:59:32+00:00" in caption
    assert "completed-cache read only" in caption
    assert "Benzinga: 20 articles" in caption
    assert "FMP: 465 articles" in caption
    assert "newest 2026-10-01T12:32:00+00:00 (28.0m old)" in caption
    assert "TipRanks absent from complete FMP window" in caption


def test_gs623_brief_does_not_schedule_live_news_poll():
    source = Path("mide/authorities/discovery_news.py").read_text(encoding="utf-8")
    start = source.index("def build_on_demand_catalyst_brief(")
    end = source.index("\ndef build_seed_symbols(*args, **kwargs):", start)
    block = source[start:end]

    assert "gs620.cache_snapshot(now=current)" in block
    assert "schedule_live_news_poll(" not in block
    assert "request_scan(" not in block
    assert "qualified_for_entry" not in block

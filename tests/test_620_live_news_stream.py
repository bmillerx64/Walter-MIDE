from datetime import datetime, timedelta, timezone
from pathlib import Path
import threading

from mide import gs309_current_attention_mission as gs309
from mide import gs620_live_news_stream as gs620


UTC = timezone.utc
NOW = datetime(2026, 9, 30, 16, 45, tzinfo=UTC)


def _reset():
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


class NewsClient:
    provider_name = "Alpaca Market Data"

    def __init__(self, rows=None):
        self.rows = list(rows or [])
        self.calls = []

    def news(self, start, limit=200, *, symbols=None, sort="desc"):
        self.calls.append({
            "start": start,
            "limit": limit,
            "symbols": symbols,
            "sort": sort,
        })
        return list(self.rows)


class LiveClient:
    provider_name = "Webull OpenAPI"

    def __init__(self, news_client):
        self._universe_client = news_client
        self.diagnostics = {}


def row(symbol, headline, *, minutes=1, source="benzinga"):
    return {
        "id": f"{symbol}-{minutes}",
        "headline": headline,
        "created_at": (NOW - timedelta(minutes=minutes)).isoformat(),
        "updated_at": (NOW - timedelta(minutes=minutes)).isoformat(),
        "symbols": [symbol],
        "source": source,
        "url": f"https://example.test/{symbol}",
    }


def test_gs620_marketwide_alpaca_poll_is_unsymbolized_and_fresh():
    _reset()
    news = NewsClient([
        row("PUSA", "Powerus to complete merger with Aureus Greenway Holdings", minutes=2),
        row("FNGR", "FingerMotion to acquire Newbit for $2.3 million in cash", minutes=4),
    ])

    articles, trace = gs620.poll_alpaca_live_news(news, now=NOW)

    assert len(articles) == 2
    assert news.calls == [{
        "start": NOW - gs620.LOOKBACK,
        "limit": gs620.MAX_ARTICLES,
        "symbols": None,
        "sort": "desc",
    }]
    assert trace["marketwide"] is True
    assert trace["endpoint"] == "/v1beta1/news"
    assert trace["newest_age_seconds"] == 120.0
    assert trace["trading_authority_changed"] is False


def test_gs620_completed_cache_adds_news_identity_on_next_scan():
    _reset()
    news = NewsClient()
    polled, _ = gs620.poll_alpaca_live_news(
        NewsClient([
            row("PUSA", "Powerus to complete merger with Aureus Greenway Holdings", minutes=2),
        ]),
        now=NOW,
    )
    gs620._store_articles(polled, now=NOW)

    client = LiveClient(news)
    seeds, reasons, trace = gs620.merge_cached_live_news(
        client,
        ["NATIVE"],
        {"NATIVE": ["Webull native: day_gainers"]},
        now=NOW,
    )

    assert "PUSA" in seeds
    assert any(
        reason.startswith(gs620.MATERIAL_REASON)
        for reason in reasons["PUSA"]
    )
    assert trace["symbols_added"] == ["PUSA"]
    assert trace["scan_blocked"] is False
    assert client.diagnostics[gs620.DIAGNOSTIC_KEY]["provider"] == "Alpaca market news"


def test_gs620_live_news_reason_is_current_attention_provenance():
    record = {
        "discovery_reasons": [
            "Alpaca live material news seed: benzinga",
        ]
    }

    assert gs309.current_attention_provenance(record) == ("FRESH_NEWS_SEED",)


def test_gs620_scheduler_returns_while_news_transport_is_blocked():
    _reset()
    entered = threading.Event()
    release = threading.Event()

    class BlockingNewsClient:
        provider_name = "Alpaca Market Data"

        def news(self, start, limit=200, *, symbols=None, sort="desc"):
            entered.set()
            release.wait(timeout=2)
            return []

    client = LiveClient(BlockingNewsClient())
    runtime = gs620.schedule_live_news_poll(client, now=NOW)

    assert runtime["status"] == "polling"
    assert entered.wait(timeout=1)
    with gs620._LOCK:
        thread = gs620._JOB
    assert isinstance(thread, threading.Thread)
    assert thread.is_alive()

    release.set()
    thread.join(timeout=2)
    assert not thread.is_alive()


def test_gs620_fmp_fallback_and_trading_authority_are_untouched():
    source = Path("mide/gs620_live_news_stream.py").read_text(encoding="utf-8")
    startup = Path("mide/startup.py").read_text(encoding="utf-8")

    assert "install_gs618()" in startup
    assert startup.index("install_gs618()") < startup.index("install_gs620()")
    assert "install_gs620()" in startup

    forbidden = (
        "qualified_for_entry =",
        "qualified_for_alert =",
        "qualified_for_watch =",
        "participation_score =",
        "expansion_score =",
        "place_order(",
        "submit_order(",
        "execute_order(",
    )
    assert not any(token in source for token in forbidden)

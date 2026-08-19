from datetime import datetime, timedelta, timezone

from mide.news_provider import FMPNewsProvider, NewsArticle, NewsProvider, NewsService


UTC = timezone.utc
NOW = datetime(2026, 8, 19, 16, 0, tzinfo=UTC)


class StaticProvider(NewsProvider):
    name = "Financial Modeling Prep news"

    def __init__(self, articles):
        self.articles = list(articles)
        self.request_count = 2
        self.last_since = NOW - timedelta(hours=6)
        self.endpoints_requested = ["news/stock", "news/press-releases"]

    def fetch(self, *, since, symbols=()):
        return list(self.articles)


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class RecordingSession:
    def __init__(self):
        self.calls = []

    def get(self, url, *, params, timeout):
        self.calls.append((url, dict(params), timeout))
        return FakeResponse([])


def article(symbol, headline, age_minutes, source="Benzinga"):
    created = NOW - timedelta(minutes=age_minutes)
    return NewsArticle(
        id=f"{symbol}-{age_minutes}",
        headline=headline,
        created_at=created,
        updated_at=None,
        symbols=[symbol],
        source=source,
        url=f"https://example.invalid/{symbol}/{age_minutes}",
        provider="Financial Modeling Prep",
    )


def test_news_service_records_symbol_freshness_and_classifier_result(tmp_path):
    provider = StaticProvider([
        article("AZI", "Autozi Internet Technology receives $30M investment", 180),
        article("BIVI", "BIVI announces strategic partnership", 20),
    ])
    service = NewsService(
        [provider], state_path=tmp_path / "news.json", now=lambda: NOW
    )

    returned = service.fetch(symbols=["AZI", "BIVI", "NONE"], force_lookback=True)

    assert len(returned) == 2
    assert service.metrics["active_provider"] == "Financial Modeling Prep news"
    assert service.metrics["requested_symbols"] == ["AZI", "BIVI", "NONE"]
    assert service.metrics["provider_endpoints"] == [
        "news/stock", "news/press-releases"
    ]
    assert service.metrics["effective_provider_since"] == (
        NOW - timedelta(hours=6)
    ).isoformat()
    assert service.metrics["symbols_with_articles"] == ["AZI", "BIVI"]
    assert service.metrics["symbols_without_articles"] == ["NONE"]

    azi = service.metrics["newest_articles_by_symbol"]["AZI"]
    assert azi["articles_returned"] == 1
    assert azi["newest_article_age_minutes"] == 180.0
    assert azi["newest_headline"] == (
        "Autozi Internet Technology receives $30M investment"
    )
    # This is diagnostic evidence, not a behavior change: it exposes that the
    # current headline classifier does not treat this observed catalyst as material.
    assert azi["newest_catalyst_score"] == 0
    assert azi["material_article_count"] == 0

    bivi = service.metrics["newest_articles_by_symbol"]["BIVI"]
    assert bivi["newest_article_age_minutes"] == 20.0
    assert bivi["newest_catalyst_score"] >= 7
    assert bivi["material_article_count"] == 1


def test_fmp_provider_records_direct_endpoints_and_six_hour_effective_window():
    session = RecordingSession()
    provider = FMPNewsProvider(
        "TOP_SECRET_KEY", session=session, now=lambda: NOW
    )

    provider.fetch(since=NOW - timedelta(days=3), symbols=["AZI", "BIVI"])

    assert provider.last_since == NOW - timedelta(hours=6)
    assert provider.last_requested_symbols == ["AZI", "BIVI"]
    assert provider.endpoints_requested == ["news/stock", "news/press-releases"]
    assert [call[0] for call in session.calls] == [
        "https://financialmodelingprep.com/stable/news/stock",
        "https://financialmodelingprep.com/stable/news/press-releases",
    ]
    assert all(call[1]["symbols"] == "AZI,BIVI" for call in session.calls)


def test_news_trace_diagnostics_never_expose_fmp_api_key(tmp_path):
    session = RecordingSession()
    provider = FMPNewsProvider(
        "TOP_SECRET_KEY", session=session, now=lambda: NOW
    )
    service = NewsService(
        [provider], state_path=tmp_path / "news.json", now=lambda: NOW
    )

    service.fetch(symbols=["AZI"], force_lookback=True)

    serialized = repr(service.metrics)
    assert "TOP_SECRET_KEY" not in serialized
    assert "apikey" not in serialized.lower()

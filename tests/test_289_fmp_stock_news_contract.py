"""GS289: lock FMP intake to entitled Stock News and auditable catalyst provenance."""

from datetime import datetime, timedelta, timezone

from mide.news_provider import FMPNewsProvider, NewsService


UTC = timezone.utc
NOW = datetime(2026, 8, 19, 19, 0, tzinfo=UTC)


class Response:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class Session:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def get(self, url, *, params, timeout):
        self.calls.append((url, dict(params), timeout))
        return Response(self.payload)


def test_fmp_stock_news_only_and_trace_selected_material_article(tmp_path):
    session = Session([
        {
            "symbol": "AZI",
            "title": "Autozi Internet Technology receives $30M investment from investors",
            "publishedDate": "2026-08-19T16:00:00+00:00",
            "publisher": "Benzinga",
            "url": "https://example.invalid/azi-investment",
        },
        {
            "symbol": "AZI",
            "title": "Autozi Internet Technology provides corporate update",
            "publishedDate": "2026-08-19T18:30:00+00:00",
            "publisher": "Benzinga",
            "url": "https://example.invalid/azi-update",
        },
    ])
    provider = FMPNewsProvider("test-key", session=session, now=lambda: NOW)
    service = NewsService([provider], state_path=tmp_path / "news.json", now=lambda: NOW)

    returned = service.fetch(
        symbols=["AZI", "NONE"],
        initial_lookback=timedelta(hours=6),
        force_lookback=True,
    )

    assert len(returned) == 2
    assert provider.endpoints_requested == ["news/stock"]
    assert provider.request_count == 1
    assert len(session.calls) == 1
    assert session.calls[0][0].endswith("/news/stock")
    assert "press-releases" not in session.calls[0][0]

    assert service.metrics["provider_endpoints"] == ["news/stock"]
    assert service.metrics["articles_received"] == 2
    assert service.metrics["symbols_with_articles"] == ["AZI"]
    assert service.metrics["symbols_without_articles"] == ["NONE"]

    trace = service.metrics["newest_articles_by_symbol"]["AZI"]
    assert trace["articles_returned"] == 2
    assert trace["newest_headline"] == "Autozi Internet Technology provides corporate update"
    assert trace["newest_catalyst_score"] == 0
    assert trace["material_article_count"] == 1
    assert trace["selected_material_headline"] == (
        "Autozi Internet Technology receives $30M investment from investors"
    )
    assert trace["selected_material_score"] >= 7
    assert "capital_injection" in trace["selected_material_flags"]


def test_fmp_batches_never_expand_beyond_stock_news():
    session = Session([])
    provider = FMPNewsProvider("test-key", session=session, now=lambda: NOW)
    symbols = [f"T{i:02d}" for i in range(41)]

    provider.fetch(since=NOW - timedelta(hours=6), symbols=symbols)

    # BATCH_SIZE=20 -> 3 requests, all to the one entitled endpoint.
    assert provider.request_count == 3
    assert provider.endpoints_requested == ["news/stock", "news/stock", "news/stock"]
    assert len(session.calls) == 3
    assert all(call[0].endswith("/news/stock") for call in session.calls)
    assert all("press-releases" not in call[0] for call in session.calls)

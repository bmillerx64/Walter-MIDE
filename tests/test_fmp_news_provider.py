from datetime import datetime, timezone

from mide.news_provider import FMPNewsProvider, NewsService, UnavailableNewsProvider


UTC = timezone.utc


class Response:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class Session:
    def __init__(self):
        self.calls = []

    def get(self, url, params=None, timeout=None):
        self.calls.append((url, dict(params or {})))
        if url.endswith("news/stock"):
            return Response([{
                "symbol": "PLAG",
                "publishedDate": "2026-08-11T13:30:00Z",
                "publisher": "PR Newswire",
                "title": "Planet Green announces strategic contract",
                "url": "https://example.test/plag",
            }])
        return Response([{
            "symbol": "PLAG",
            "date": "2026-08-11T13:35:00Z",
            "title": "Planet Green issues company press release",
            "url": "https://example.test/plag-release",
        }])


def test_fmp_news_preserves_provider_symbol_metadata_and_wire_source():
    session = Session()
    provider = FMPNewsProvider("secret", session=session)
    articles = provider.fetch(
        since=datetime(2026, 8, 11, 13, 0, tzinfo=UTC), symbols=["PLAG"]
    )

    assert len(articles) == 2
    assert all(article.symbols == ["PLAG"] for article in articles)
    assert articles[0].source == "PR Newswire"
    assert provider.request_count == 2
    assert all(call[1]["symbols"] == "PLAG" for call in session.calls)


def test_fmp_news_batches_symbols_at_twenty():
    session = Session()
    provider = FMPNewsProvider("secret", session=session)
    symbols = [f"S{i}" for i in range(41)]
    provider.fetch(since=datetime(2026, 8, 11, 13, 0, tzinfo=UTC), symbols=symbols)

    stock_calls = [params for url, params in session.calls if url.endswith("news/stock")]
    assert [len(params["symbols"].split(",")) for params in stock_calls] == [20, 20, 1]


def test_live_webull_unavailable_seam_upgrades_to_fmp_when_key_exists(monkeypatch, tmp_path):
    monkeypatch.setenv("FMP_API_KEY", "configured")
    service = NewsService(
        [UnavailableNewsProvider("Webull raw news unavailable", "no raw article feed")],
        state_path=tmp_path / "news.json",
    )
    assert isinstance(service.providers[0], FMPNewsProvider)
    assert isinstance(service.providers[-1], UnavailableNewsProvider)

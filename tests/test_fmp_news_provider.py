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
        return Response([{
            "symbol": "PLAG",
            "publishedDate": "2026-08-11T13:30:00Z",
            "publisher": "PR Newswire",
            "title": "Planet Green announces strategic contract",
            "url": "https://example.test/plag",
        }])


def test_fmp_news_preserves_provider_symbol_metadata_and_wire_source():
    session = Session()
    provider = FMPNewsProvider("secret", session=session)
    articles = provider.fetch(
        since=datetime(2026, 8, 11, 13, 0, tzinfo=UTC), symbols=["PLAG"]
    )

    assert len(articles) == 1
    assert articles[0].symbols == ["PLAG"]
    assert articles[0].source == "PR Newswire"
    assert provider.request_count == 1
    assert len(session.calls) == 1
    assert session.calls[0][0].endswith("news/stock")
    assert session.calls[0][1]["symbols"] == "PLAG"


def test_fmp_news_batches_symbols_at_twenty():
    session = Session()
    provider = FMPNewsProvider("secret", session=session)
    symbols = [f"S{i}" for i in range(41)]
    provider.fetch(since=datetime(2026, 8, 11, 13, 0, tzinfo=UTC), symbols=symbols)

    stock_calls = [params for url, params in session.calls if url.endswith("news/stock")]
    batch_sizes = sorted(len(params["symbols"].split(",")) for params in stock_calls)
    assert batch_sizes == [1, 20, 20]
    assert len(stock_calls) == 3


def test_live_webull_unavailable_seam_upgrades_to_fmp_when_key_exists(monkeypatch, tmp_path):
    monkeypatch.setenv("FMP_API_KEY", "configured")
    service = NewsService(
        [UnavailableNewsProvider("Webull raw news unavailable", "no raw article feed")],
        state_path=tmp_path / "news.json",
    )
    assert isinstance(service.providers[0], FMPNewsProvider)
    assert isinstance(service.providers[-1], UnavailableNewsProvider)

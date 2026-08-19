"""GS287 regression: Walter must not request FMP endpoints outside the subscribed plan."""

from datetime import datetime, timezone

from mide.gs285_fmp_latency import install
from mide.news_provider import FMPNewsProvider


UTC = timezone.utc


class Response:
    def raise_for_status(self):
        return None

    def json(self):
        return []


class Session:
    def __init__(self):
        self.urls = []

    def get(self, url, *, params, timeout):
        self.urls.append(url)
        return Response()


def test_fmp_runtime_requests_only_entitled_stock_news():
    install()
    session = Session()
    provider = FMPNewsProvider(
        "test-key",
        session=session,
        now=lambda: datetime(2026, 8, 19, 18, 0, tzinfo=UTC),
    )

    provider.fetch(
        since=datetime(2026, 8, 19, 12, 0, tzinfo=UTC),
        symbols=["BIVI", "TEST"],
    )

    assert provider.endpoints_requested == ["news/stock"]
    assert provider.request_count == 1
    assert len(session.urls) == 1
    assert session.urls[0].endswith("/news/stock")
    assert all("press-releases" not in url for url in session.urls)

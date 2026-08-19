from datetime import datetime, timedelta, timezone
from time import perf_counter, sleep

import requests

from mide.news_provider import FMPNewsProvider

UTC = timezone.utc
NOW = datetime(2026, 8, 19, 17, 0, tzinfo=UTC)


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload
    def raise_for_status(self):
        return None
    def json(self):
        return self.payload


class SlowSession:
    def __init__(self, delay=0.12):
        self.delay = delay
        self.calls = []
    def get(self, url, *, params, timeout):
        self.calls.append((url, timeout))
        sleep(self.delay)
        return FakeResponse([])


class PartialFailureSession:
    def get(self, url, *, params, timeout):
        if url.endswith("press-releases"):
            raise requests.Timeout("simulated bounded timeout")
        return FakeResponse([{
            "symbol": "AZI",
            "title": "Autozi Internet Technology receives $30M investment",
            "publishedDate": "2026-08-19T16:30:00+00:00",
            "publisher": "Benzinga",
        }])


def test_fmp_defaults_to_bounded_four_second_http_timeout():
    provider = FMPNewsProvider("secret", session=SlowSession(), now=lambda: NOW)
    assert provider.timeout == 4


def test_fmp_batches_and_endpoints_run_concurrently():
    session = SlowSession()
    provider = FMPNewsProvider("secret", session=session, now=lambda: NOW)
    symbols = [f"S{i}" for i in range(35)]
    started = perf_counter()
    provider.fetch(since=NOW - timedelta(hours=2), symbols=symbols)
    elapsed = perf_counter() - started
    assert provider.request_count == 4
    assert len(session.calls) == 4
    assert elapsed < 0.38


def test_one_fmp_endpoint_failure_preserves_successful_news():
    provider = FMPNewsProvider("secret", session=PartialFailureSession(), now=lambda: NOW)
    articles = provider.fetch(since=NOW - timedelta(hours=2), symbols=["AZI"])
    assert len(articles) == 1
    assert articles[0].symbols == ["AZI"]
    assert provider.request_count == 2
    assert len(provider.request_failures) == 1
    assert "press-releases" in provider.request_failures[0]
    assert "secret" not in repr(provider.request_failures)

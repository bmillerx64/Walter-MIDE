from __future__ import annotations

import sys
from types import SimpleNamespace

import mide.gs257_runtime as gs257
import mide.news_provider as news_provider
import mide.webull_native_radar as radar


class Secrets(dict):
    pass


def test_fmp_resolver_reads_nested_streamlit_secret(monkeypatch):
    monkeypatch.delenv("FMP_API_KEY", raising=False)
    fake_streamlit = SimpleNamespace(secrets=Secrets({"fmp": {"api_key": "runtime-secret"}}))
    monkeypatch.setitem(sys.modules, "streamlit", fake_streamlit)
    assert gs257._streamlit_secret_value() == "runtime-secret"


def test_news_service_uses_runtime_fmp_resolver(monkeypatch, tmp_path):
    monkeypatch.setattr(news_provider, "_configured_fmp_api_key", lambda: "runtime-secret")
    service = news_provider.NewsService(
        [news_provider.UnavailableNewsProvider("Webull raw news unavailable", "no raw feed")],
        state_path=tmp_path / "news.json",
    )
    assert service.providers[0].name == "Financial Modeling Prep news"


def test_expanded_webull_radar_requests_three_pages(monkeypatch):
    calls = []

    class Screener:
        def get_gainers_losers(self, **kwargs):
            calls.append(("gainers", kwargs["page_index"]))
            return {"data": [{"symbol": f"G{kwargs['page_index']}{i}"} for i in range(20)]}

        def get_most_active(self, **kwargs):
            calls.append(("active", kwargs["page_index"]))
            return {"data": [{"symbol": f"A{kwargs['page_index']}{i}"} for i in range(20)]}

    monkeypatch.setattr(radar, "_resolve_screener", lambda _client: Screener())
    gs257.install()
    report = radar.fetch_native_radar(object())

    assert report["all_feeds_available"] is True
    assert report["pages_requested_per_feed"] == 3
    assert len(calls) == 12
    assert {page for _, page in calls} == {1, 2, 3}
    assert report["unique_symbols"] > 71

from datetime import datetime, timezone
from unittest.mock import patch, Mock

from mide.alpaca import AlpacaClient


def response(payload):
    r = Mock()
    r.status_code = 200
    r.json.return_value = payload
    return r


def test_news_paginates_and_never_requests_over_50():
    client = AlpacaClient("k", "s", feed="sip")
    first = {"news": [{"id": i} for i in range(50)], "next_page_token": "next"}
    second = {"news": [{"id": i} for i in range(50, 75)]}
    with patch("mide.alpaca.requests.get", side_effect=[response(first), response(second)]) as get:
        items = client.news(datetime.now(timezone.utc), limit=75)
    assert len(items) == 75
    assert get.call_args_list[0].kwargs["params"]["limit"] == 50
    assert get.call_args_list[1].kwargs["params"]["limit"] == 25


def test_bars_paginates_across_symbols():
    client = AlpacaClient("k", "s", feed="sip")
    first = {"bars": {"AAA": [{"t": "2026-01-01T00:00:00Z"}]}, "next_page_token": "next"}
    second = {"bars": {"BBB": [{"t": "2026-01-01T00:00:00Z"}]}}
    with patch("mide.alpaca.requests.get", side_effect=[response(first), response(second)]):
        bars = client.bars(["AAA", "BBB"], datetime.now(timezone.utc))
    assert len(bars["AAA"]) == 1
    assert len(bars["BBB"]) == 1

def test_screener_limits_are_capped_at_50(monkeypatch):
    client = AlpacaClient("key", "secret", feed="sip")
    calls = []

    def fake_get(base, path, params=None):
        calls.append((path, dict(params or {})))
        if "movers" in path:
            return {"gainers": [], "losers": []}
        return {"most_actives": []}

    monkeypatch.setattr(client, "_get", fake_get)
    client.movers(500)
    client.most_actives(500)
    assert calls[0][1]["top"] == 50
    assert calls[1][1]["top"] == 50

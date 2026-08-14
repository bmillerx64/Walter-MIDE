import mide.webull_connection as connection


class Provider:
    def __init__(self): self.diagnostics = {}


def test_native_assets_returns_webull_symbols_and_marks_no_alpaca(monkeypatch):
    monkeypatch.setattr(connection, "fetch_native_radar", lambda _client: {
        "feeds": {
            key: {"status": "PASS", "error": "", "rows": [{"symbol": "AAA"}]}
            for key in ("day_gainers", "five_minute_movers", "relative_volume", "absolute_volume")
        },
        "symbols": [{"symbol": "AAA", "name": "AAA Inc", "sources": ["day_gainers"],
                     "ranks": {"day_gainers": 1}}],
    })
    provider = Provider()
    assets = connection._webull_native_assets(provider)
    assert [row["symbol"] for row in assets] == ["AAA"]
    assert provider.diagnostics["webull_native_discovery"]["alpaca_universe_used"] is False
    assert provider.diagnostics["market_data_sources"]["universe_provider"] == "Webull OpenAPI SDK native radar"

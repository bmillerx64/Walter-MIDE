from mide.webull_live import LiveWebullProvider


class _Rest:
    def snapshots(self, symbols):
        return {symbol: {"latestTrade": {"p": 1.0}, "dailyBar": {"c": 1.0, "v": 1000},
                         "market_data_provider": "Webull OpenAPI SDK"} for symbol in symbols}

    def bars(self, symbols, **kwargs):
        return {symbol: [] for symbol in symbols}


class _ForbiddenUniverse:
    def assets(self):
        raise AssertionError("legacy Alpaca universe must never be called")


def test_live_webull_provenance_is_authoritative_and_fallback_free():
    provider = LiveWebullProvider("key", "secret", rest_client=_Rest(),
                                 universe_client=_ForbiddenUniverse())
    contract = provider.diagnostics["live_evidence_contract"]
    assert contract["mode"] == "LIVE_WEBULL"
    assert contract["discovery"] == "Webull OpenAPI SDK native radar"
    assert contract["quotes"] == "Webull OpenAPI SDK"
    assert contract["bars"] == "Webull OpenAPI SDK"
    assert contract["fallback_market_data_allowed"] is False
    assert contract["alpaca_runtime_enabled"] is False
    assert provider._universe_client is None


def test_pipeline_sources_report_no_alpaca_market_data():
    provider = LiveWebullProvider("key", "secret", rest_client=_Rest())
    rows = provider.pipeline_sources()
    assert rows
    assert all(row["Alpaca used"] == "No" for row in rows)
    market_rows = [row for row in rows if row["Stage"] != "News / catalyst"]
    assert all("Alpaca" not in row["Actual provider"] for row in market_rows)
    assert rows[0]["Actual provider"] == "Webull OpenAPI SDK native radar"

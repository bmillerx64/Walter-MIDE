import pytest

import mide.webull_connection as connection
from mide.webull_live import LiveWebullProvider


class FakeProvider:
    def __init__(self):
        self.diagnostics = {}
        self.warnings = []
        self._universe_client = object()


def _report(*symbols):
    rows = [
        {"symbol": symbol, "sources": ["day_gainers"], "ranks": {"day_gainers": rank}}
        for rank, symbol in enumerate(symbols, 1)
    ]
    return {
        "feeds": {
            "day_gainers": {"status": "PASS", "rows": rows, "error": ""},
            "five_minute_movers": {"status": "PASS", "rows": [], "error": ""},
            "relative_volume": {"status": "PASS", "rows": [], "error": ""},
            "absolute_volume": {"status": "PASS", "rows": [], "error": ""},
        },
        "symbols": rows,
    }


def test_live_webull_assets_are_webull_native_and_ignore_alpaca_universe(monkeypatch):
    provider = FakeProvider()
    monkeypatch.setattr(connection, "fetch_native_radar", lambda _provider: _report("WETO", "CAPR"))

    assets = connection._webull_native_assets(provider)

    assert [asset["symbol"] for asset in assets] == ["WETO", "CAPR"]
    assert all(asset["tradable"] and asset["status"] == "active" for asset in assets)
    assert provider.diagnostics["webull_native_discovery"]["alpaca_universe_used"] is False
    assert provider.diagnostics["webull_native_discovery"]["unique_symbols"] == 2
    assert provider.diagnostics["broad_source"] == "Webull native market attention"


def test_live_webull_native_discovery_fails_closed_without_alpaca_fallback(monkeypatch):
    provider = FakeProvider()
    report = _report("WETO")
    report["feeds"]["day_gainers"] = {
        "status": "FAIL", "rows": [], "error": "403 Insufficient permission"
    }
    monkeypatch.setattr(connection, "fetch_native_radar", lambda _provider: report)

    with pytest.raises(RuntimeError, match="403 Insufficient permission"):
        connection._webull_native_assets(provider)


def test_imported_live_webull_class_uses_native_discovery_patch():
    assert LiveWebullProvider.assets is connection._webull_native_assets
    assert getattr(LiveWebullProvider.assets, "_walter_webull_native_discovery", False) is True

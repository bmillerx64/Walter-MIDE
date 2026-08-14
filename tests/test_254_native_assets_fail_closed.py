import pytest

import mide.webull_connection as connection


class Provider:
    diagnostics = {}


def test_native_assets_rejects_zero_symbol_success(monkeypatch):
    monkeypatch.setattr(connection, "fetch_native_radar", lambda _client: {
        "feeds": {
            "day_gainers": {"status": "PASS", "error": "", "rows": [{}]},
            "five_minute_movers": {"status": "PASS", "error": "", "rows": [{}]},
            "relative_volume": {"status": "PASS", "error": "", "rows": [{}]},
            "absolute_volume": {"status": "PASS", "error": "", "rows": [{}]},
        },
        "symbols": [],
    })

    with pytest.raises(RuntimeError, match="zero symbols"):
        connection._webull_native_assets(Provider())

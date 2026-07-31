from datetime import datetime, timezone
import json
from unittest.mock import patch, Mock

from mide.alpaca import AlpacaClient, credential_status


def response(payload):
    r = Mock()
    r.status_code = 200
    r.headers = {"content-type": "application/json"}
    r.text = json.dumps(payload)
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


def test_news_supports_structured_ticker_targeting_and_incremental_order():
    client = AlpacaClient("k", "s", feed="sip")
    with patch("mide.alpaca.requests.get", return_value=response({"news": []})) as get:
        client.news(
            datetime.now(timezone.utc),
            limit=50,
            symbols=["cycu", "CYCU", "test"],
            sort="asc",
        )
    assert get.call_args.kwargs["params"]["symbols"] == "CYCU,TEST"
    assert get.call_args.kwargs["params"]["sort"] == "asc"


def test_bars_paginates_across_symbols():
    client = AlpacaClient("k", "s", feed="sip")
    first = {"bars": {"AAA": [{"t": "2026-01-01T00:00:00Z"}]}, "next_page_token": "next"}
    second = {"bars": {"BBB": [{"t": "2026-01-01T00:00:00Z"}]}}
    with patch("mide.alpaca.requests.get", side_effect=[response(first), response(second)]):
        bars = client.bars(["AAA", "BBB"], datetime.now(timezone.utc))
    assert len(bars["AAA"]) == 1
    assert len(bars["BBB"]) == 1


def test_free_float_diagnostic_captures_request_response_fields_and_reason():
    client = AlpacaClient("key", "secret", feed="sip", timeout=12)
    raw = {"latestTrade": {"p": 1.25}, "dailyBar": {"c": 1.2}}
    mocked_response = response(raw)
    mocked_response.request.url = (
        "https://data.alpaca.markets/v2/stocks/NCRA/snapshot?feed=sip"
    )

    with patch("mide.alpaca.requests.get", return_value=mocked_response) as get:
        diagnostic = client.free_float_diagnostic("ncra")

    get.assert_called_once_with(
        "https://data.alpaca.markets/v2/stocks/NCRA/snapshot",
        headers=client.headers,
        params={"feed": "sip"},
        timeout=12,
    )
    assert diagnostic["request"]["headers"] == {
        "APCA-API-KEY-ID": "<redacted>",
        "APCA-API-SECRET-KEY": "<redacted>",
    }
    assert diagnostic["response"]["json"] == raw
    assert set(diagnostic["parsed_fields"]) == {
        "float_shares", "shares_float", "free_float", "float_millions"
    }
    assert diagnostic["fields_found"] == []
    assert diagnostic["lookup_succeeded"] is False
    assert diagnostic["failure_reason"] == (
        "Alpaca snapshot response contains none of the supported free-float fields: "
        "float_shares, shares_float, free_float, float_millions"
    )

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


def test_latest_trades_retrieves_only_price_evidence(monkeypatch):
    client = AlpacaClient("key", "secret", feed="iex")
    calls = []

    def fake_get(base, path, params=None):
        calls.append((path, params))
        return {"trades": {"KEEP": {"p": 1.25}, "DROP": {"p": 8.0}}}

    monkeypatch.setattr(client, "_get", fake_get)

    assert client.latest_trades(["keep", "DROP", "keep"]) == {
        "KEEP": 1.25,
        "DROP": 8.0,
    }
    assert calls == [(
        "/v2/stocks/trades/latest",
        {"symbols": "DROP,KEEP", "feed": "iex"},
    )]


def test_credential_status_checks_paper_before_live_and_records_diagnostics(monkeypatch):
    client = AlpacaClient(" key ", " secret ", feed="sip")
    calls = []

    def fake_get(base, path, params=None, *, authenticated=True):
        calls.append((base, path, dict(params or {}), authenticated))
        return {"status": "ACTIVE"}

    monkeypatch.setattr(client, "_get", fake_get)
    assert client.credential_status() == "paper"
    assert calls == [(client.PAPER_TRADING, "/v2/account", {}, True)]
    assert client.diagnostics["credential_environment"] == "paper"
    assert client.diagnostics["account_status"] == "ACTIVE"
    assert client.headers["APCA-API-KEY-ID"] == "key"
    assert client.headers["APCA-API-SECRET-KEY"] == "secret"


def test_assets_accepts_asset_class_field_and_records_counts(monkeypatch):
    client = AlpacaClient("key", "secret", feed="sip")

    def fake_get(base, path, params=None, *, authenticated=True):
        return [
            {"symbol": "GOOD", "name": "Good Corp Common Stock", "tradable": True, "status": "active", "asset_class": "us_equity"},
            {"symbol": "BAD", "tradable": False, "status": "active", "asset_class": "us_equity"},
            {"symbol": "ODD", "name": "Odd Corp Units", "tradable": True, "status": "active", "asset_class": "us_equity"},
            {"symbol": "WRONG", "name": "Wrong Corp Common Stock", "tradable": True, "status": "active", "asset_class": "crypto"},
        ]

    monkeypatch.setattr(client, "_get", fake_get)
    assets = client.assets()
    assert [item["symbol"] for item in assets] == ["GOOD"]
    assert client.diagnostics["assets_endpoint"] == "paper"
    assert client.diagnostics["assets_raw"] == 4
    assert client.diagnostics["assets_eligible"] == 1
    assert client.diagnostics["assets_non_common_rejected"] == 1


def test_assets_classifies_instruments_from_metadata_not_symbol(monkeypatch):
    client = AlpacaClient("key", "secret")
    monkeypatch.setattr(client, "_get", lambda *args, **kwargs: [
        {"symbol": "KEEP.W", "name": "Keep Incorporated Common Stock", "tradable": True,
         "status": "active", "class": "us_equity"},
        {"symbol": "PLAIN", "name": "Plain Incorporated Warrant", "tradable": True,
         "status": "active", "class": "us_equity"},
        {"symbol": "PREF", "name": "Example Depositary Shares Preferred Stock", "tradable": True,
         "status": "active", "class": "us_equity"},
    ])

    assert [asset["symbol"] for asset in client.assets()] == ["KEEP.W"]


def test_bars_limit_is_capped_at_10000(monkeypatch):
    client = AlpacaClient("key", "secret", feed="sip")
    calls = []

    def fake_get(base, path, params=None, *, authenticated=True):
        calls.append(dict(params or {}))
        return {"bars": {}}

    monkeypatch.setattr(client, "_get", fake_get)
    client.bars(["AAA"], datetime.now(timezone.utc), limit=25_000)
    assert calls[0]["limit"] == 10_000


def test_free_float_probe_logs_raw_alpaca_fields_and_explicitly_missing_float(monkeypatch):
    client = AlpacaClient("key", "secret", feed="sip")
    raw = {
        "NCRA": {
            "dailyBar": {"c": 1.23, "v": 456},
            "latestTrade": {"p": 1.24},
            "minuteBar": {"c": 1.24},
            "prevDailyBar": {"c": 1.10},
        }
    }
    calls = []

    def fake_get(base, path, params=None, *, authenticated=True):
        calls.append((base, path, dict(params or {})))
        return raw

    monkeypatch.setattr(client, "_get", fake_get)
    evidence = client.free_float_probe("ncra")

    assert calls == [(client.DATA, "/v2/stocks/snapshots", {"symbols": "NCRA", "feed": "sip"})]
    assert evidence["provider"] == "Alpaca"
    assert evidence["request_succeeded"] is True
    assert evidence["raw_response"] == raw
    assert evidence["json_fields"] == [
        "dailyBar", "latestTrade", "minuteBar", "prevDailyBar"
    ]
    assert evidence["free_float_field_present"] is False
    assert evidence["free_float_status"] == (
        "MISSING: Alpaca snapshot supplied no Free Float field"
    )


def test_free_float_probe_distinguishes_request_failure_from_missing_field(monkeypatch):
    client = AlpacaClient("key", "secret")

    def fail(*args, **kwargs):
        raise RuntimeError("network unavailable")

    monkeypatch.setattr(client, "_get", fail)
    evidence = client.free_float_probe("NCRA")

    assert evidence["request_succeeded"] is False
    assert evidence["raw_response"] is None
    assert evidence["free_float_status"] == "UNKNOWN: request failed"
    assert evidence["error"] == "network unavailable"


def test_module_credential_status_supports_legacy_client_without_method():
    class LegacyClient:
        PAPER_TRADING = "paper-base"
        LIVE_TRADING = "live-base"

        def __init__(self):
            self.diagnostics = {}
            self.calls = []

        def _get(self, base, path, params=None, *, authenticated=True):
            self.calls.append((base, path, dict(params or {}), authenticated))
            return {"status": "ACTIVE"}

    client = LegacyClient()

    assert credential_status(client) == "paper"
    assert client.calls == [("paper-base", "/v2/account", {}, True)]
    assert client.diagnostics["credential_environment"] == "paper"
    assert client.diagnostics["account_status"] == "ACTIVE"

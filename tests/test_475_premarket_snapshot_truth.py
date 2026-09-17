from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from mide import gs475_premarket_snapshot_truth as gs475
from mide import webull_sdk
from mide.webull_live import WebullOpenAPIClient


ET = ZoneInfo("America/New_York")


def _et(hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 9, 17, hour, minute, tzinfo=ET)


def _payload(**overrides):
    row = {
        "symbol": "HOT",
        "price": "1.43",
        "pre_close": "1.46",
        "volume": "23000000",
        "last_trade_time": 100,
        "ext_price": "8.37",
        "ext_trade_time": 200,
        "ovn_price": "7.90",
        "ovn_trade_time": 300,
    }
    row.update(overrides)
    return {"data": [row]}


def test_premarket_uses_extended_price_without_rewriting_volume_or_previous_close():
    result = gs475.apply_snapshot_session_truth(_payload(), now_et=_et(8, 26))
    row = result["data"][0]

    assert row["price"] == "8.37"
    assert row["last_trade_time"] == 200
    assert row["volume"] == "23000000"
    assert row["pre_close"] == "1.46"
    assert row["_walter_regular_session_price"] == "1.43"
    assert row["_walter_snapshot_price_source"] == "ext_price"
    assert row["_walter_snapshot_session"] == "PRE"


def test_after_hours_uses_extended_price_but_rth_preserves_regular_price():
    after_hours = gs475.apply_snapshot_session_truth(_payload(), now_et=_et(16, 30))
    assert after_hours["data"][0]["price"] == "8.37"
    assert after_hours["data"][0]["_walter_snapshot_session"] == "ATH"

    rth = gs475.apply_snapshot_session_truth(_payload(), now_et=_et(10, 15))
    assert rth["data"][0]["price"] == "1.43"
    assert rth["data"][0]["last_trade_time"] == 100
    assert "_walter_snapshot_price_source" not in rth["data"][0]


def test_overnight_falls_back_to_regular_snapshot_truth():
    overnight = gs475.apply_snapshot_session_truth(_payload(), now_et=_et(21, 0))
    assert overnight["data"][0]["price"] == "1.43"
    assert overnight["data"][0]["last_trade_time"] == 100
    assert "_walter_snapshot_price_source" not in overnight["data"][0]


def test_gs476_premarket_requests_extended_without_night_entitlement(monkeypatch):
    calls = []

    class SDK:
        def get_snapshot(self, **kwargs):
            calls.append(kwargs)
            return _payload()

    original = webull_sdk.WebullSDKClient.stock_snapshot
    monkeypatch.setattr(gs475, "_now_eastern", lambda: _et(8, 26))
    try:
        gs475.install()
        client = WebullOpenAPIClient("k", "s", sdk_client=SDK())
        snapshots = client.snapshots(["HOT"])
    finally:
        webull_sdk.WebullSDKClient.stock_snapshot = original

    assert calls == [{
        "symbols": "HOT",
        "category": "US_STOCK",
        "extend_hour_required": True,
    }]
    assert snapshots["HOT"]["latestTrade"]["p"] == 8.37
    assert snapshots["HOT"]["latestTrade"]["t"] == 200
    assert snapshots["HOT"]["dailyBar"]["v"] == 23000000.0
    assert snapshots["HOT"]["prevDailyBar"]["c"] == 1.46


def test_gs476_rth_uses_plain_snapshot_request(monkeypatch):
    calls = []

    class SDK:
        def get_snapshot(self, **kwargs):
            calls.append(kwargs)
            return _payload()

    original = webull_sdk.WebullSDKClient.stock_snapshot
    monkeypatch.setattr(gs475, "_now_eastern", lambda: _et(10, 23))
    try:
        gs475.install()
        client = WebullOpenAPIClient("k", "s", sdk_client=SDK())
        snapshots = client.snapshots(["HOT"])
    finally:
        webull_sdk.WebullSDKClient.stock_snapshot = original

    assert calls == [{"symbols": "HOT", "category": "US_STOCK"}]
    assert snapshots["HOT"]["latestTrade"]["p"] == 1.43


def test_gs476_overnight_never_requests_night_feed(monkeypatch):
    calls = []

    class SDK:
        def get_snapshot(self, **kwargs):
            calls.append(kwargs)
            return _payload()

    original = webull_sdk.WebullSDKClient.stock_snapshot
    monkeypatch.setattr(gs475, "_now_eastern", lambda: _et(21, 0))
    try:
        gs475.install()
        client = WebullOpenAPIClient("k", "s", sdk_client=SDK())
        snapshots = client.snapshots(["HOT"])
    finally:
        webull_sdk.WebullSDKClient.stock_snapshot = original

    assert calls == [{"symbols": "HOT", "category": "US_STOCK"}]
    assert snapshots["HOT"]["latestTrade"]["p"] == 1.43


def test_gs476_replaces_retained_gs475_wrapper(monkeypatch):
    calls = []

    def base_stock_snapshot(self, symbols, *, extended_hours=False):
        calls.append((tuple(symbols), extended_hours))
        return _payload()

    def retained_gs475(self, symbols, *, extended_hours=False):
        raise AssertionError("retained GS475 wrapper must be unwrapped, not stacked")

    retained_gs475._gs475_original = base_stock_snapshot
    setattr(retained_gs475, gs475.LEGACY_OWNER_ATTR, True)

    original = webull_sdk.WebullSDKClient.stock_snapshot
    monkeypatch.setattr(webull_sdk.WebullSDKClient, "stock_snapshot", retained_gs475)
    monkeypatch.setattr(gs475, "_now_eastern", lambda: _et(10, 23))
    try:
        gs475.install()
        wrapped = webull_sdk.WebullSDKClient.stock_snapshot
        client = object.__new__(webull_sdk.WebullSDKClient)
        result = client.stock_snapshot(["HOT"])

        assert calls == [(('HOT',), False)]
        assert result["data"][0]["price"] == "1.43"
        assert client.last_snapshot_extended_requested is False
        assert client.last_snapshot_overnight_requested is False
        assert getattr(wrapped, gs475.OWNER_ATTR, False) is True

        gs475.install()
        assert webull_sdk.WebullSDKClient.stock_snapshot is wrapped
    finally:
        webull_sdk.WebullSDKClient.stock_snapshot = original


def test_gs475_is_bound_before_final_late_runtime_presentation_chain():
    source = Path("mide/gs414_final_enriched_opportunity_order.py").read_text(encoding="utf-8")
    assert "gs475_premarket_snapshot_truth" in source
    install_body = source.split("def install() -> None:", 1)[1]
    assert install_body.index("_install_gs475()") < install_body.index("_install_gs464()")


def test_gs476_scope_is_data_truth_and_transport_safety_only():
    source = Path("mide/gs475_premarket_snapshot_truth.py").read_text(encoding="utf-8")

    assert "WebullSDKClient.stock_snapshot = stock_snapshot_with_session_truth" in source
    assert "extend_hour_required=True" in source
    assert "overnight_required=True" not in source
    assert "ext_price" in source
    assert "scanner_v2" not in source
    assert "trader_priority_sort_key" not in source
    assert "qualified_for_entry =" not in source
    assert "qualified_for_alert =" not in source

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


def test_overnight_uses_overnight_price_only_when_it_is_usable():
    overnight = gs475.apply_snapshot_session_truth(_payload(), now_et=_et(21, 0))
    assert overnight["data"][0]["price"] == "7.90"
    assert overnight["data"][0]["last_trade_time"] == 300
    assert overnight["data"][0]["_walter_snapshot_session"] == "OVN"

    missing = gs475.apply_snapshot_session_truth(
        _payload(ovn_price="0", ovn_trade_time=None), now_et=_et(21, 0)
    )
    assert missing["data"][0]["price"] == "1.43"
    assert missing["data"][0]["last_trade_time"] == 100


def test_gs475_forces_optional_extended_fields_and_self_heals_warm_sdk_instances(monkeypatch):
    calls = []

    def base_stock_snapshot(self, symbols, *, extended_hours=False):
        calls.append((tuple(symbols), extended_hours))
        return _payload()

    original = webull_sdk.WebullSDKClient.stock_snapshot
    monkeypatch.setattr(webull_sdk.WebullSDKClient, "stock_snapshot", base_stock_snapshot)
    monkeypatch.setattr(gs475, "_now_eastern", lambda: _et(8, 26))

    try:
        gs475.install()
        wrapped = webull_sdk.WebullSDKClient.stock_snapshot
        client = object.__new__(webull_sdk.WebullSDKClient)
        result = client.stock_snapshot(["HOT"])

        assert calls == [(('HOT',), True)]
        assert result["data"][0]["price"] == "8.37"
        assert client.last_snapshot_extended_requested is True
        assert client.last_snapshot_session_price_field == "ext_price"
        assert getattr(wrapped, gs475.OWNER_ATTR, False) is True

        gs475.install()
        assert webull_sdk.WebullSDKClient.stock_snapshot is wrapped
    finally:
        # gs475.install() directly replaces the class attribute after monkeypatch has
        # recorded its own value. Restore the real pre-test callable explicitly so
        # this regression cannot leak the runtime installer into unrelated SDK tests.
        webull_sdk.WebullSDKClient.stock_snapshot = original


def test_gs475_flows_through_existing_webull_normalization(monkeypatch):
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
        "overnight_required": True,
    }]
    assert snapshots["HOT"]["latestTrade"]["p"] == 8.37
    assert snapshots["HOT"]["latestTrade"]["t"] == 200
    assert snapshots["HOT"]["dailyBar"]["v"] == 23000000.0
    assert snapshots["HOT"]["prevDailyBar"]["c"] == 1.46


def test_gs475_is_bound_before_final_late_runtime_presentation_chain():
    source = Path("mide/gs414_final_enriched_opportunity_order.py").read_text(encoding="utf-8")
    assert "gs475_premarket_snapshot_truth" in source
    install_body = source.split("def install() -> None:", 1)[1]
    assert install_body.index("_install_gs475()") < install_body.index("_install_gs464()")


def test_gs475_scope_is_data_truth_only():
    source = Path("mide/gs475_premarket_snapshot_truth.py").read_text(encoding="utf-8")

    assert "WebullSDKClient.stock_snapshot = stock_snapshot_with_session_truth" in source
    assert "extended_hours=True" in source
    assert "ext_price" in source and "ovn_price" in source
    assert "scanner_v2" not in source
    assert "trader_priority_sort_key" not in source
    assert "qualified_for_entry =" not in source
    assert "qualified_for_alert =" not in source

from mide.webull_native_radar import fetch_native_radar, radar_probe_rows
from mide.webull_connection import run_connection_test

class FakeScreener:
    def __init__(self): self.calls=[]
    def get_gainers_losers(self, **kwargs):
        self.calls.append(("get_gainers_losers", kwargs)); prefix="D" if kwargs["rank_type"]=="DAY_1" else "M"
        return {"data":[{"symbol":f"{prefix}{i}","name":f"{prefix} name {i}","price":1.0+i,"change_ratio":10.0+i,"volume":100_000*i,"relative_volume_10d":2.0+i} for i in range(1,4)]}
    def get_most_active(self, **kwargs):
        self.calls.append(("get_most_active", kwargs)); prefix="R" if kwargs["rank_type"]=="RELATIVE_VOLUME_10D" else "V"
        return {"result":[{"ticker_symbol":f"{prefix}{i}","last_price":2.0+i,"pct_change":5.0+i,"total_volume":200_000*i,"rvol":3.0+i} for i in range(1,4)]}
class FakeRawSDK:
    def __init__(self): self.screener=FakeScreener()
class FakeSDKAdapter:
    def __init__(self): self.sdk_client=FakeRawSDK()
class FakeSnapshotClient:
    def __init__(self): self.sdk=FakeSDKAdapter()
class FakeLiveClient:
    def __init__(self,*_args): self._snapshot_client=FakeSnapshotClient()
    def snapshots(self,symbols): return {s:{"latestTrade":{"p":1.0}} for s in symbols}

def test_native_radar_calls_three_feed_discovery_contract():
    client=FakeLiveClient(); report=fetch_native_radar(client)
    assert report["all_feeds_available"] is True
    # 3 unique symbols per feed, R prefix overlaps with V prefix via deduplication only when same symbol
    assert report["discovery_feed_keys"]==["day_gainers","absolute_volume","relative_volume"]
    calls=client._snapshot_client.sdk.sdk_client.screener.calls
    assert [c[0] for c in calls]==["get_gainers_losers","get_most_active","get_most_active"]
    assert calls[0][1]["rank_type"]=="DAY_1" and calls[1][1]["rank_type"]=="VOLUME" and calls[2][1]["rank_type"]=="RELATIVE_VOLUME_10D"
    assert all(c[1]["page_size"]==20 and c[1]["page_index"]==1 for c in calls)

def test_native_radar_normalizes_rows_and_provenance():
    report=fetch_native_radar(FakeLiveClient()); day=report["feeds"]["day_gainers"]["rows"][0]
    assert day["symbol"]=="D1" and day["price"]==2.0 and day["source_feed"]=="day_gainers"
    assert report["symbols"][0]["sources"]==["day_gainers"] and report["symbols"][0]["ranks"]=={"day_gainers":1}

def test_native_radar_records_permission_errors_on_scanned_feed():
    class BrokenScreener(FakeScreener):
        def get_most_active(self,**kwargs): raise RuntimeError("403 Insufficient permission")
    client=FakeLiveClient(); client._snapshot_client.sdk.sdk_client.screener=BrokenScreener(); report=fetch_native_radar(client)
    assert report["all_feeds_available"] is False
    assert report["feeds"]["day_gainers"]["status"]=="PASS"
    assert report["feeds"]["absolute_volume"]["status"]=="FAIL"
    assert "403 Insufficient permission" in report["feeds"]["absolute_volume"]["error"]
    # relative_volume also uses get_most_active, so it too fails
    assert report["feeds"]["relative_volume"]["status"]=="FAIL"

def test_connection_test_surfaces_radar_rows_after_snapshot_validation():
    rows=run_connection_test(app_key="key",app_secret="secret",eligible_symbols=[f"S{i}" for i in range(12)],client_factory=FakeLiveClient)
    radar_rows=[r for r in rows if r["Test"].startswith("Native radar")]
    assert len(radar_rows)==4
    by_test={r["Test"]:r for r in radar_rows}
    assert by_test["Native radar — DAY GAINERS"]["Status"]=="PASS"
    assert by_test["Native radar — ABSOLUTE VOLUME"]["Status"]=="PASS"
    assert by_test["Native radar — 5-MINUTE MOVERS"]["Status"]=="NOT_SCANNED"
    assert by_test["Native radar — RELATIVE VOLUME"]["Status"]=="PASS"

def test_connection_test_preserves_snapshot_validation_when_screener_is_absent():
    class SnapshotOnlyClient:
        def __init__(self,*_args): pass
        def snapshots(self,symbols): return {s:{} for s in symbols}
    rows=run_connection_test(app_key="key",app_secret="secret",eligible_symbols=[f"S{i}" for i in range(12)],client_factory=SnapshotOnlyClient)
    assert rows[0]["Test"]=="Credential loading" and rows[1]["Test"]=="SDK client initialization" and rows[2]["Test"]=="HYFM snapshot"
    radar_rows=[r for r in rows if r["Test"].startswith("Native radar")]
    assert len(radar_rows)==4 and all(r["Status"]=="FAIL" for r in radar_rows)

def test_missing_screener_fails_closed():
    try: fetch_native_radar(object())
    except RuntimeError as exc: assert "get_gainers_losers/get_most_active" in str(exc)
    else: raise AssertionError("Expected missing screener to fail closed")

def test_rvol_all_below_gain_threshold_is_not_a_feed_failure():
    """RVOL symbols with <2% gain are filtered out; zero post-filter rows is
    a normal dead-tape condition and must not mark the feed as FAIL."""
    class LowGainScreener(FakeScreener):
        def get_most_active(self, **kwargs):
            self.calls.append(("get_most_active", kwargs))
            if kwargs.get("rank_type") == "RELATIVE_VOLUME_10D":
                # All RVOL symbols are flat / declining — below the 2% threshold
                return {"result": [{"ticker_symbol": f"RX{i}", "last_price": 1.0+i,
                                    "pct_change": 0.5, "total_volume": 100_000*i, "rvol": 5.0+i}
                                   for i in range(1, 4)]}
            prefix = "V"
            return {"result": [{"ticker_symbol": f"{prefix}{i}", "last_price": 2.0+i,
                                "pct_change": 5.0+i, "total_volume": 200_000*i, "rvol": 3.0+i}
                               for i in range(1, 4)]}

    client = FakeLiveClient()
    client._snapshot_client.sdk.sdk_client.screener = LowGainScreener()
    report = fetch_native_radar(client)
    # relative_volume API responded fine; filtered result is zero — must still be PASS
    assert report["feeds"]["relative_volume"]["status"] == "PASS"
    assert report["feeds"]["relative_volume"]["rows"] == []
    # Other feeds are unaffected; overall availability is still True
    assert report["feeds"]["day_gainers"]["status"] == "PASS"
    assert report["feeds"]["absolute_volume"]["status"] == "PASS"
    assert report["all_feeds_available"] is True
    # Universe symbols come from the two non-RVOL feeds
    symbols = {s["symbol"] for s in report["symbols"]}
    assert symbols  # day_gainers + absolute_volume contribute symbols
    assert not any(s.startswith("RX") for s in symbols)

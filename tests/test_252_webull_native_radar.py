from mide.webull_native_radar import fetch_native_radar, radar_probe_rows
from mide.webull_connection import run_connection_test


class FakeScreener:
    def __init__(self):
        self.calls = []

    def get_gainers_losers(self, **kwargs):
        self.calls.append(("get_gainers_losers", kwargs))
        prefix = "D" if kwargs["rank_type"] == "DAY_1" else "M"
        return {
            "data": [
                {
                    "symbol": f"{prefix}{index}",
                    "name": f"{prefix} name {index}",
                    "price": 1.0 + index,
                    "change_ratio": 10.0 + index,
                    "volume": 100_000 * index,
                    "relative_volume_10d": 2.0 + index,
                }
                for index in range(1, 4)
            ]
        }

    def get_most_active(self, **kwargs):
        self.calls.append(("get_most_active", kwargs))
        prefix = "R" if kwargs["rank_type"] == "RELATIVE_VOLUME_10D" else "V"
        return {
            "result": [
                {
                    "ticker_symbol": f"{prefix}{index}",
                    "last_price": 2.0 + index,
                    "pct_change": 5.0 + index,
                    "total_volume": 200_000 * index,
                    "rvol": 3.0 + index,
                }
                for index in range(1, 4)
            ]
        }


class FakeRawSDK:
    def __init__(self):
        self.screener = FakeScreener()


class FakeSDKAdapter:
    def __init__(self):
        self.sdk_client = FakeRawSDK()


class FakeSnapshotClient:
    def __init__(self):
        self.sdk = FakeSDKAdapter()


class FakeLiveClient:
    def __init__(self, *_args):
        self._snapshot_client = FakeSnapshotClient()

    def snapshots(self, symbols):
        return {symbol: {"latestTrade": {"p": 1.0}} for symbol in symbols}


def test_native_radar_calls_official_four_feed_contracts():
    client = FakeLiveClient()
    report = fetch_native_radar(client)

    assert report["all_feeds_available"] is True
    assert report["unique_symbols"] == 12
    assert [call[0] for call in client._snapshot_client.sdk.sdk_client.screener.calls] == [
        "get_gainers_losers",
        "get_gainers_losers",
        "get_most_active",
        "get_most_active",
    ]

    calls = client._snapshot_client.sdk.sdk_client.screener.calls
    assert calls[0][1] == {
        "rank_type": "DAY_1", "category": "US_STOCK", "sort_by": "CHANGE_RATIO",
        "direction": "DESC", "page_index": 1, "page_size": 20,
    }
    assert calls[1][1]["rank_type"] == "MIN_5"
    assert calls[2][1]["rank_type"] == "RELATIVE_VOLUME_10D"
    assert calls[3][1]["rank_type"] == "VOLUME"


def test_native_radar_normalizes_rows_and_provenance():
    report = fetch_native_radar(FakeLiveClient())
    day = report["feeds"]["day_gainers"]["rows"][0]
    assert day == {
        "rank": 1,
        "symbol": "D1",
        "name": "D name 1",
        "price": 2.0,
        "change": None,
        "change_ratio": 11.0,
        "volume": 100000.0,
        "relative_volume_10d": 3.0,
        "market_value": None,
        "turnover_rate": None,
        "amplitude": None,
        "instrument_id": None,
        "source_feed": "day_gainers",
        "source_label": "DAY GAINERS",
    }
    assert report["symbols"][0]["sources"] == ["day_gainers"]
    assert report["symbols"][0]["ranks"] == {"day_gainers": 1}


def test_native_radar_records_permission_or_sdk_errors_without_hiding_them():
    class BrokenScreener(FakeScreener):
        def get_most_active(self, **kwargs):
            raise RuntimeError("403 Insufficient permission")

    client = FakeLiveClient()
    client._snapshot_client.sdk.sdk_client.screener = BrokenScreener()
    report = fetch_native_radar(client)

    assert report["all_feeds_available"] is False
    assert report["feeds"]["day_gainers"]["status"] == "PASS"
    assert report["feeds"]["relative_volume"]["status"] == "FAIL"
    assert "403 Insufficient permission" in report["feeds"]["relative_volume"]["error"]


def test_connection_test_surfaces_native_radar_rows_after_snapshot_validation():
    rows = run_connection_test(
        app_key="key",
        app_secret="secret",
        eligible_symbols=[f"S{index}" for index in range(12)],
        client_factory=FakeLiveClient,
    )

    radar_rows = [row for row in rows if row["Test"].startswith("Native radar")]
    assert len(radar_rows) == 4
    assert all(row["Status"] == "PASS" for row in radar_rows)
    assert radar_rows[0]["Returned symbol count"] == 3
    assert radar_rows[0]["First 10 returned symbols"] == "D1, D2, D3"
    assert radar_rows[0]["Endpoint / SDK operation"] == "screener.get_gainers_losers"


def test_missing_screener_fails_closed():
    class NoScreener:
        pass

    try:
        fetch_native_radar(NoScreener())
    except RuntimeError as exc:
        assert "get_gainers_losers/get_most_active" in str(exc)
    else:
        raise AssertionError("Expected missing screener to fail closed")

from mide.webull_native_radar import fetch_native_radar


class Response:
    status_code = 200

    def __init__(self, symbol):
        self.symbol = symbol

    def json(self):
        return {
            "data": [
                {
                    "symbol": self.symbol,
                    "name": f"{self.symbol} Inc",
                    "price": "1.25",
                    "change_ratio": "42.0",
                    "volume": "2500000",
                    "relative_volume_10d": "7.5",
                }
            ]
        }


class Screener:
    def get_gainers_losers(self, **kwargs):
        return Response("GAIN" if kwargs["rank_type"] == "DAY_1" else "M5")

    def get_most_active(self, **kwargs):
        return Response("RVOL" if kwargs["rank_type"] == "RELATIVE_VOLUME_10D" else "VOL")


class RawDataClient:
    def __init__(self):
        self.screener = Screener()


class SDKAdapter:
    def __init__(self):
        self.sdk_client = RawDataClient()


class SnapshotClient:
    def __init__(self):
        self.sdk = SDKAdapter()


class LiveProviderShape:
    def __init__(self):
        self._snapshot_client = SnapshotClient()


def test_native_radar_decodes_official_response_json_through_live_wrapper_graph():
    report = fetch_native_radar(LiveProviderShape())

    assert report["all_feeds_available"] is True
    assert report["unique_symbols"] == 4
    assert {row["symbol"] for row in report["symbols"]} == {"GAIN", "M5", "RVOL", "VOL"}
    assert report["feeds"]["day_gainers"]["rows"][0]["price"] == 1.25


def test_native_radar_fails_closed_when_official_response_has_no_rows():
    class EmptyResponse:
        status_code = 200
        def json(self):
            return {"data": []}

    class EmptyScreener:
        def get_gainers_losers(self, **_kwargs): return EmptyResponse()
        def get_most_active(self, **_kwargs): return EmptyResponse()

    report = fetch_native_radar(EmptyScreener())

    assert report["all_feeds_available"] is False
    assert report["unique_symbols"] == 0
    assert all(feed["status"] == "FAIL" for feed in report["feeds"].values())
    assert all("zero ranking rows" in feed["error"] for feed in report["feeds"].values())

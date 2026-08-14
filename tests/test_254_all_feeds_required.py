from mide.webull_native_radar import fetch_native_radar


class OneFailure:
    def get_gainers_losers(self, **kwargs):
        class R:
            status_code = 200
            def json(self): return {"data": [{"symbol": kwargs["rank_type"]}]}
        return R()
    def get_most_active(self, **kwargs):
        if kwargs["rank_type"] == "VOLUME":
            raise RuntimeError("boom")
        class R:
            status_code = 200
            def json(self): return {"data": [{"symbol": "RVOL"}]}
        return R()


def test_native_radar_requires_every_configured_feed():
    report = fetch_native_radar(OneFailure())
    assert report["all_feeds_available"] is False

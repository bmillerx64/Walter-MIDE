from mide.gs339_preignition_vwap_reclaim import preignition_watch, Snapshot


def test_static_constructive_reading_is_not_promoted():
    prior = Snapshot(30, 46, 300000, True, 1.0)
    record = {
        "symbol": "TEST",
        "vwap_distance_pct": 1.0,
        "supertrend_bullish": True,
        "participation_score": 30,
        "expansion_score": 46,
        "volume": 320000,
    }
    assert preignition_watch(record, prior) == (False, "no fresh reclaim or strengthening")

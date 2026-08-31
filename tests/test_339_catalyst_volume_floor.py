from mide.gs339_preignition_vwap_reclaim import preignition_watch, Snapshot


def test_fresh_news_can_corroborate_lower_absolute_volume():
    prior = Snapshot(20, 38, 50000, False, 1.0)
    record = {
        "symbol": "TEST",
        "vwap_distance_pct": 0.8,
        "supertrend_bullish": True,
        "participation_score": 30,
        "expansion_score": 46,
        "volume": 60000,
        "fresh_news": True,
    }
    assert preignition_watch(record, prior)[0] is True

from mide.gs339_preignition_vwap_reclaim import preignition_watch, Snapshot


def test_reclaim_cue_never_surfaces_below_vwap():
    prior = Snapshot(20, 38, 300000, False, 1.0)
    record = {
        "symbol": "TEST",
        "vwap_distance_pct": -0.1,
        "supertrend_bullish": True,
        "participation_score": 60,
        "expansion_score": 70,
        "volume": 500000,
    }
    assert preignition_watch(record, prior) == (False, "below VWAP")

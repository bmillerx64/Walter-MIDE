from mide.gs339_preignition_vwap_reclaim import watch_recommendation


def test_watch_recommendation_is_non_entry_language():
    prior = type("P", (), {"participation": 20.0, "expansion": 38.0, "volume": 300000.0, "above_vwap": False, "seen_at": 1.0})()
    record = {
        "symbol": "SQFT",
        "vwap_distance_pct": 1.0,
        "supertrend_bullish": True,
        "participation_score": 30,
        "expansion_score": 46,
        "volume": 360000,
    }
    rec = watch_recommendation(record, prior)
    assert rec is not None
    assert "WATCH CLOSELY" in rec["label"]
    assert "entry-ready" in rec["message"]

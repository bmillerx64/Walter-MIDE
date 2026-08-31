from mide.gs339_preignition_vwap_reclaim import apply_preignition_marks, reset_preignition_memory


def test_apply_marks_requires_consecutive_scan_transition():
    reset_preignition_memory()
    first = [{
        "symbol": "VBIO",
        "vwap_distance_pct": -0.4,
        "supertrend_bullish": True,
        "participation_score": 22,
        "expansion_score": 40,
        "volume": 300000,
    }]
    second = [{
        "symbol": "VBIO",
        "vwap_distance_pct": 1.1,
        "supertrend_bullish": True,
        "participation_score": 32,
        "expansion_score": 46,
        "volume": 360000,
    }]
    assert "_gs339_preignition_watch" not in apply_preignition_marks(first, now=1.0)[0]
    marked = apply_preignition_marks(second, now=61.0)[0]
    assert marked["_gs339_preignition_watch"]["label"] == "SETUP BUILDING · WATCH CLOSELY"

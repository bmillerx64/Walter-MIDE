from mide.scoring import Evidence, score


def base(**updates):
    values = dict(
        symbol="TEST", price=.50, pct_change=20, volume=5_000_000,
        dollar_volume=2_500_000, spread_pct=1.0, vwap_relation="above",
        vwap_distance_pct=.2, supertrend_bullish=True, supertrend_flip=True,
        ema65_relation="above", ema65_distance_pct=.3, volume_acceleration=2.0,
        green_volume_ratio=2.0, rvol_proxy=5.0, higher_lows=True, near_hod=True,
        catalyst_score=10, headline="Company wins contract", news_age_hours=2,
        risk_flags=[], timeframe_confirmations=4, discovery_reasons=["market mover"]
    )
    values.update(updates)
    return Evidence(**values)


def test_aligned_setup_is_elevated():
    result = score(base())
    assert result.status in {"MONITOR", "WATCH NOW", "ALERT", "EXCEPTIONAL"}
    assert result.opportunity_score >= 60


def test_offering_is_pass():
    result = score(base(
        headline="Company announces registered direct offering",
        catalyst_score=-28, risk_flags=["registered direct", "offering"]
    ))
    assert result.status == "PASS"


def test_no_news_can_still_elevate():
    result = score(base(headline="", catalyst_score=0, news_age_hours=None))
    assert result.status in {"MONITOR", "WATCH NOW", "ALERT", "EXCEPTIONAL"}


def test_major_volume_scores_higher_than_modest_volume():
    modest = score(base(volume=500_000, dollar_volume=250_000, rvol_proxy=2.0))
    major = score(base(volume=50_000_000, dollar_volume=25_000_000, rvol_proxy=8.0))
    assert major.participation_score > modest.participation_score + 15
    assert major.attention_score > modest.attention_score
    assert major.participation_tier in {"EXCEPTIONAL", "DOMINANT"}


def test_dominance_is_nonzero_and_ranks_leader():
    from mide.discovery import apply_attention_ranking
    records = [
        {"symbol":"LEAD","volume":30_000_000,"dollar_volume":15_000_000,"pct_change":40,
         "rvol_proxy":8,"opportunity_score":90,"participation_score":94,"status":"ALERT","reasons":[]},
        {"symbol":"OTHER","volume":3_000_000,"dollar_volume":1_000_000,"pct_change":10,
         "rvol_proxy":2,"opportunity_score":65,"participation_score":55,"status":"MONITOR","reasons":[]},
    ]
    ranked = apply_attention_ranking(records)
    assert ranked[0]["symbol"] == "LEAD"
    assert ranked[0]["market_dominance_score"] > ranked[1]["market_dominance_score"] > 0


def test_scanner_v2_rewards_developing_momentum_without_completed_setup():
    from mide.scanner_v2 import apply_scanner_v2

    record = {
        **base(vwap_relation="below", supertrend_bullish=False, supertrend_flip=False,
               ema65_relation="below", timeframe_confirmations=0).__dict__,
        "opportunity_score": 48,
        "participation_score": 72,
        "status": "PASS",
        "timeframes": {},
        "reasons": [],
        "cautions": [],
    }
    ranked = apply_scanner_v2([record], {})
    assert ranked[0]["candidate_status"] in {"Watching", "Emerging", "Strengthening"}
    assert "accelerating volume" in " ".join(ranked[0]["reasons"])


def test_scanner_v2_alerts_only_when_entering_or_advancing_watch_state():
    from mide.scanner_v2 import apply_scanner_v2

    prior = {
        "TEST": {
            "candidate_status": "Watching",
            "scanner_v2_score": 40,
            "volume": 1_000_000,
            "dollar_volume": 500_000,
            "rvol_proxy": 1.5,
            "opportunity_score": 45,
            "vwap_relation": "below",
        }
    }
    record = {
        **base(timeframe_confirmations=3).__dict__,
        "opportunity_score": 70,
        "participation_score": 80,
        "status": "MONITOR",
        "timeframes": {
            "1m": {"above_vwap": True, "supertrend": True},
            "3m": {"above_vwap": True, "supertrend": True},
            "5m": {"above_vwap": True, "supertrend": True},
        },
        "reasons": [],
        "cautions": [],
    }
    ranked = apply_scanner_v2([record], prior)
    assert ranked[0]["candidate_status"] in {"Strengthening", "Entry Ready"}
    assert ranked[0]["advanced_state"] is True
    assert ranked[0]["alert_event"] is True

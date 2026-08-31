from mide.gs340_high_liquidity_trend_watch import high_liquidity_trend_rows


def test_gs340_does_not_claim_trade_qualification_fields():
    rows = [{
        "symbol": "GPRO",
        "change_ratio": 46.0,
        "price": 0.88,
        "volume": 166_000_000,
        "sources": ["day_gainers"],
        "ranks": {"day_gainers": 4},
    }]
    event = high_liquidity_trend_rows(rows)[0]

    assert event["attention_only"] is True
    for key in ("qualified", "entry_ready", "readiness", "participation_score", "expansion_score"):
        assert key not in event

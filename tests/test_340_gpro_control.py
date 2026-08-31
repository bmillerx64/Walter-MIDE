from mide import gs334_market_event_lane as lane


def test_gpro_live_control_would_remain_visible():
    rows = [{
        "symbol": "GPRO",
        "change_ratio": 46.06,
        "price": 0.8762,
        "volume": 166_120_000,
        "sources": ["day_gainers"],
        "ranks": {"day_gainers": 4},
    }]

    events = lane.market_event_rows(rows)

    assert [event["symbol"] for event in events] == ["GPRO"]
    assert events[0]["attention_only"] is True
    assert events[0]["event_type"] == "high_liquidity_trend"

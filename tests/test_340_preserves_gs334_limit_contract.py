from mide import gs334_market_event_lane as lane


def test_gs340_preserves_requested_extreme_mover_limit_before_adding_liquidity_watch():
    rows = [
        {"symbol": "A", "change_ratio": 120.0, "price": 1.0, "volume": 1_000_000, "sources": ["day_gainers"], "ranks": {"day_gainers": 1}},
        {"symbol": "B", "change_ratio": 110.0, "price": 1.0, "volume": 1_000_000, "sources": ["day_gainers"], "ranks": {"day_gainers": 2}},
        {"symbol": "GPRO", "change_ratio": 46.0, "price": 0.88, "volume": 166_000_000, "sources": ["day_gainers"], "ranks": {"day_gainers": 4}},
    ]

    events = lane.market_event_rows(rows, limit=1)

    assert [event["symbol"] for event in events] == ["A", "GPRO"]

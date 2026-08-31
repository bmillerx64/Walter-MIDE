from mide import gs334_market_event_lane as lane


def test_gs340_is_installed_after_gs334():
    assert getattr(lane.market_event_rows, "_gs340_high_liquidity_trend_watch", False)

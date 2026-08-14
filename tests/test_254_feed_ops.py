from mide.webull_native_radar import RADAR_FEEDS


def test_native_feeds_use_only_official_screener_operations():
    assert {feed.operation for feed in RADAR_FEEDS} == {"get_gainers_losers", "get_most_active"}

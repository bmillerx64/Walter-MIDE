from mide.webull_native_radar import RADAR_FEEDS


def test_all_native_radar_feeds_request_twenty_rows():
    assert all(feed.arguments["page_size"] == 20 for feed in RADAR_FEEDS)

from mide.webull_native_radar import RADAR_FEEDS


def test_native_feed_labels_cover_market_attention_inputs():
    assert [feed.label for feed in RADAR_FEEDS] == [
        "DAY GAINERS", "5-MINUTE MOVERS", "RELATIVE VOLUME", "ABSOLUTE VOLUME"
    ]

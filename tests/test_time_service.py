from datetime import datetime, timezone

from mide.time_service import format_eastern_time, market_clock, market_phase_at


def test_last_scan_displays_eastern_daylight_time_from_utc():
    utc_scan_time = datetime(2026, 7, 22, 21, 42, 18, tzinfo=timezone.utc)

    assert format_eastern_time(utc_scan_time) == "5:42:18 PM EDT"


def test_last_scan_displays_eastern_standard_time_from_utc():
    utc_scan_time = datetime(2026, 1, 22, 22, 42, 18, tzinfo=timezone.utc)

    assert format_eastern_time(utc_scan_time) == "5:42:18 PM EST"


def test_main_page_banner_displays_eastern_time_and_phase():
    clock = market_clock(datetime(2026, 7, 22, 21, 42, 18, tzinfo=timezone.utc))

    assert clock.banner_text == "Market Time: 5:42:18 PM EDT | After Hours"


def test_last_scan_and_banner_share_same_eastern_rendered_time():
    current_time = datetime(2026, 7, 22, 13, 42, 18, tzinfo=timezone.utc)
    clock = market_clock(current_time)

    assert format_eastern_time(current_time) == clock.time_text
    assert clock.banner_text.startswith(f"Market Time: {clock.time_text} | ")


def test_market_phase_is_derived_from_same_eastern_time_source():
    pre_market = market_clock(datetime(2026, 7, 22, 13, 29, 59, tzinfo=timezone.utc))
    market_open = market_clock(datetime(2026, 7, 22, 13, 30, 0, tzinfo=timezone.utc))
    after_hours = market_clock(datetime(2026, 7, 22, 20, 0, 0, tzinfo=timezone.utc))

    assert pre_market.time_text == "9:29:59 AM EDT"
    assert pre_market.phase == market_phase_at(pre_market.now) == "Pre-Market"
    assert market_open.time_text == "9:30:00 AM EDT"
    assert market_open.phase == market_phase_at(market_open.now) == "Market Open"
    assert after_hours.time_text == "4:00:00 PM EDT"
    assert after_hours.phase == market_phase_at(after_hours.now) == "After Hours"

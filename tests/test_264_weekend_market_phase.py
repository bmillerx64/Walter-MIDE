from datetime import datetime

from mide.time_service import market_clock, market_phase_at


def test_saturday_midday_cannot_be_live_market():
    current = datetime(2026, 8, 15, 10, 16, 0)
    assert market_phase_at(current) == "Market Closed"
    assert market_clock(current).banner_text.endswith("| Market Closed")


def test_sunday_after_hours_clock_time_is_still_closed():
    current = datetime(2026, 8, 16, 17, 30, 0)
    assert market_phase_at(current) == "Market Closed"

"""Gold Standard contracts for Walter's user-facing U.S. market session clock."""

from datetime import datetime, timezone

from mide.time_service import market_clock, market_phase_at


def test_evening_runtime_is_market_closed_after_extended_hours():
    # 8:32 PM EDT is after the 8:00 PM extended-hours close.
    clock = market_clock(datetime(2026, 8, 13, 0, 32, 17, tzinfo=timezone.utc))
    assert clock.time_text == "8:32:17 PM EDT"
    assert clock.phase == "Market Closed"


def test_session_boundaries_use_single_eastern_clock():
    cases = [
        (datetime(2026, 8, 12, 7, 59, 59, tzinfo=timezone.utc), "Market Closed"),
        (datetime(2026, 8, 12, 8, 0, 0, tzinfo=timezone.utc), "Pre-Market"),
        (datetime(2026, 8, 12, 13, 30, 0, tzinfo=timezone.utc), "Live Market"),
        (datetime(2026, 8, 12, 20, 0, 0, tzinfo=timezone.utc), "After-Hours"),
        (datetime(2026, 8, 13, 0, 0, 0, tzinfo=timezone.utc), "Market Closed"),
    ]
    for moment, expected in cases:
        clock = market_clock(moment)
        assert clock.phase == expected
        assert market_phase_at(clock.now) == expected

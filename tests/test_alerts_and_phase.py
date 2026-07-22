from datetime import datetime
from zoneinfo import ZoneInfo

from app import market_phase, scan_alert_phrase


def test_watching_announcements_repeat_when_entry_ready_empty():
    records = [{"symbol": "AAA", "candidate_status": "Watching"}]
    assert scan_alert_phrase(records) == "Watching one."
    assert scan_alert_phrase(records) == "Watching one."


def test_watching_announcement_reports_queue_size_without_tickers():
    records = [
        {"symbol": "AAA", "candidate_status": "Watching"},
        {"symbol": "BBB", "candidate_status": "Emerging"},
        {"symbol": "CCC", "candidate_status": "Strengthening"},
    ]
    assert scan_alert_phrase(records) == "Watching three."


def test_entry_ready_suppresses_watching_announcement():
    records = [
        {"symbol": "AAA", "candidate_status": "Watching"},
        {"symbol": "INLF", "candidate_status": "Entry Ready"},
    ]
    assert scan_alert_phrase(records) == "Entry Ready - INLF."


def test_entry_ready_symbols_repeat_every_scan():
    records = [
        {"symbol": "INLF", "candidate_status": "Entry Ready"},
        {"symbol": "KUST", "candidate_status": "Entry Ready"},
    ]
    assert scan_alert_phrase(records) == "Entry Ready - INLF, KUST."
    assert scan_alert_phrase(records) == "Entry Ready - INLF, KUST."


def test_market_phase_uses_local_time_against_us_equity_hours():
    pacific = ZoneInfo("America/Los_Angeles")
    assert market_phase(datetime(2026, 7, 22, 6, 0, tzinfo=pacific)) == "Premarket discovery"
    assert market_phase(datetime(2026, 7, 22, 6, 45, tzinfo=pacific)) == "Opening momentum"
    assert market_phase(datetime(2026, 7, 22, 9, 0, tzinfo=pacific)) == "Midday validation"
    assert market_phase(datetime(2026, 7, 22, 12, 30, tzinfo=pacific)) == "Late-session momentum"
    assert market_phase(datetime(2026, 7, 22, 13, 5, tzinfo=pacific)) == "After-hours observation"

from datetime import datetime
from zoneinfo import ZoneInfo

from app import market_phase, scan_alert_phrase


def test_watch_list_is_informational_and_never_announced():
    records = [
        {"symbol": "AAA", "candidate_status": "Watching"},
        {"symbol": "BBB", "candidate_status": "Emerging"},
    ]
    assert scan_alert_phrase(records) == ""


def test_strengthening_announcement_reports_queue_size_without_tickers():
    records = [
        {"symbol": "AAA", "candidate_status": "Watching"},
        {"symbol": "BBB", "candidate_status": "Emerging"},
        {"symbol": "CCC", "candidate_status": "Strengthening"},
        {"symbol": "DDD", "candidate_status": "Strengthening"},
    ]
    assert scan_alert_phrase(records) == "Watching two."


def test_entry_ready_suppresses_watching_announcement():
    records = [
        {"symbol": "AAA", "candidate_status": "Watching"},
        {"symbol": "INLF", "candidate_status": "Entry Ready"},
    ]
    assert scan_alert_phrase(records) == "Entry Ready: INLF."


def test_entry_ready_symbols_repeat_every_scan():
    records = [
        {"symbol": "INLF", "candidate_status": "Entry Ready"},
        {"symbol": "KUST", "candidate_status": "Entry Ready"},
    ]
    assert scan_alert_phrase(records) == "Entry Ready: INLF and KUST."
    assert scan_alert_phrase(records) == "Entry Ready: INLF and KUST."


def test_market_phase_uses_local_time_against_us_equity_hours():
    pacific = ZoneInfo("America/Los_Angeles")
    assert market_phase(datetime(2026, 7, 22, 6, 0, tzinfo=pacific)) == "Pre-market"
    assert market_phase(datetime(2026, 7, 22, 6, 30, tzinfo=pacific)) == "Market Open"
    assert market_phase(datetime(2026, 7, 22, 12, 59, tzinfo=pacific)) == "Market Open"
    assert market_phase(datetime(2026, 7, 22, 13, 0, tzinfo=pacific)) == "After-hours"
    assert market_phase(datetime(2026, 7, 22, 13, 5, tzinfo=pacific)) == "After-hours"

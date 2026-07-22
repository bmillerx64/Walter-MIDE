from datetime import datetime
from zoneinfo import ZoneInfo

from app import (
    DEFAULT_VOICE,
    ALERT_VOICE_SESSION_KEY,
    alert_voice_for_session,
    market_phase,
    persisted_alert_voice,
    scan_alert_phrase,
)
from mide.ui import promoted_this_scan, state_sections


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
    assert scan_alert_phrase(records) == "Entry Ready: INLF."


def test_entry_ready_symbols_repeat_every_scan():
    records = [
        {"symbol": "INLF", "candidate_status": "Entry Ready"},
        {"symbol": "KUST", "candidate_status": "Entry Ready"},
    ]
    assert scan_alert_phrase(records) == "Entry Ready: INLF and KUST."
    assert scan_alert_phrase(records) == "Entry Ready: INLF and KUST."


def test_voice_selection_persists_during_multiple_automatic_scan_cycles():
    session = {ALERT_VOICE_SESSION_KEY: "Microsoft David"}
    auto_cycle_voices = [alert_voice_for_session(session) for _ in range(3)]
    assert auto_cycle_voices == ["Microsoft David", "Microsoft David", "Microsoft David"]


def test_voice_selection_persists_after_page_refresh_from_query_state():
    refreshed_session = {}
    assert persisted_alert_voice({"alert_voice": "Samantha"}, refreshed_session) == "Samantha"
    assert refreshed_session[ALERT_VOICE_SESSION_KEY] == "Samantha"
    assert alert_voice_for_session(refreshed_session) == "Samantha"


def test_default_voice_normalizes_to_system_default_code_path():
    session = {ALERT_VOICE_SESSION_KEY: DEFAULT_VOICE}
    assert alert_voice_for_session(session) == ""


def test_watching_promotions_are_visually_identified_only_for_current_scan():
    records = [
        {"symbol": "AAA", "candidate_status": "Watching", "entered_watchlist": True},
        {"symbol": "BBB", "candidate_status": "Watching", "entered_watchlist": False, "advanced_state": False},
    ]
    sections = state_sections(records)
    assert [r["symbol"] for r in sections["Watching"]] == ["AAA", "BBB"]
    assert promoted_this_scan(sections["Watching"][0]) is True
    assert promoted_this_scan(sections["Watching"][1]) is False


def test_entry_ready_promotions_are_visually_identified():
    record = {"symbol": "INLF", "candidate_status": "Entry Ready", "advanced_state": True}
    sections = state_sections([record])
    assert sections["Entry Ready"] == [record]
    assert promoted_this_scan(record) is True


def test_market_phase_uses_local_time_against_us_equity_hours():
    pacific = ZoneInfo("America/Los_Angeles")
    assert market_phase(datetime(2026, 7, 22, 6, 0, tzinfo=pacific)) == "Pre-market"
    assert market_phase(datetime(2026, 7, 22, 6, 30, tzinfo=pacific)) == "Market Open"
    assert market_phase(datetime(2026, 7, 22, 12, 59, tzinfo=pacific)) == "Market Open"
    assert market_phase(datetime(2026, 7, 22, 13, 0, tzinfo=pacific)) == "After-hours"
    assert market_phase(datetime(2026, 7, 22, 13, 5, tzinfo=pacific)) == "After-hours"

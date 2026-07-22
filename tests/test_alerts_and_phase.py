from datetime import datetime
from zoneinfo import ZoneInfo

from app import (
    DEFAULT_VOICE,
    VOICE_OPTIONS,
    ALERT_VOICE_SESSION_KEY,
    alert_voice_for_session,
    market_phase,
    persisted_alert_voice,
    scan_alert_phrase,
)
from mide.ui import promoted_this_scan, scanner_v2_dashboard_counts, state_sections


def test_watch_list_count_is_never_used_for_voice_alerts():
    records = [
        {"symbol": "AAA", "candidate_status": "Watching"},
        {"symbol": "BBB", "candidate_status": "Emerging"},
        {"symbol": "CCC", "candidate_status": "Strengthening"},
    ]
    assert scan_alert_phrase(records) == "Watching 1."


def test_strengthening_three_announces_watching_three():
    records = [
        {"symbol": "AAA", "candidate_status": "Strengthening"},
        {"symbol": "BBB", "candidate_status": "Strengthening"},
        {"symbol": "CCC", "candidate_status": "Strengthening"},
    ]
    assert scan_alert_phrase(records) == "Watching 3."


def test_strengthening_zero_produces_no_watching_announcement():
    records = [
        {"symbol": "AAA", "candidate_status": "Watching"},
        {"symbol": "BBB", "candidate_status": "Emerging"},
    ]
    assert scan_alert_phrase(records) == ""


def test_strengthening_metric_and_voice_alert_share_dashboard_count():
    zero_records = [
        {"symbol": "AAA", "candidate_status": "Watching", "velocity": 12},
        {"symbol": "BBB", "candidate_status": "Emerging", "velocity": 9},
    ]
    assert scanner_v2_dashboard_counts(zero_records)["strengthening"] == 0
    assert scan_alert_phrase(zero_records) == ""

    five_records = [
        {"symbol": f"ST{i}", "candidate_status": "Strengthening", "velocity": 0}
        for i in range(5)
    ]
    assert scanner_v2_dashboard_counts(five_records)["strengthening"] == 5
    assert scan_alert_phrase(five_records) == "Watching 5."

    for records in (zero_records, five_records):
        dashboard_strengthening = scanner_v2_dashboard_counts(records)["strengthening"]
        phrase = scan_alert_phrase(records)
        announced_strengthening = int(phrase.removeprefix("Watching ").removesuffix(".")) if phrase else 0
        assert announced_strengthening == dashboard_strengthening

def test_entry_ready_suppresses_watching_announcement():
    records = [
        {"symbol": "AAA", "candidate_status": "Strengthening"},
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
    session = {ALERT_VOICE_SESSION_KEY: "David"}
    auto_cycle_voices = [alert_voice_for_session(session) for _ in range(3)]
    assert auto_cycle_voices == ["David", "David", "David"]


def test_voice_selection_persists_after_page_refresh_from_query_state():
    refreshed_session = {}
    assert persisted_alert_voice({"alert_voice": "samantha-id"}, refreshed_session) == "samantha-id"
    assert refreshed_session[ALERT_VOICE_SESSION_KEY] == "samantha-id"
    assert alert_voice_for_session(refreshed_session) == "samantha-id"


def test_default_voice_normalizes_to_system_default_code_path():
    session = {ALERT_VOICE_SESSION_KEY: DEFAULT_VOICE}
    assert alert_voice_for_session(session) == ""


def test_supported_voice_options_exclude_google():
    assert VOICE_OPTIONS == [DEFAULT_VOICE]
    assert "Google US English" not in VOICE_OPTIONS


def test_david_selection_persists_during_multiple_scan_cycles():
    session = {ALERT_VOICE_SESSION_KEY: "David"}
    scan_voices = [alert_voice_for_session(session) for _ in range(3)]
    assert scan_voices == ["David", "David", "David"]


def test_unsupported_query_voice_does_not_replace_existing_selection():
    session = {ALERT_VOICE_SESSION_KEY: "Samantha"}
    assert persisted_alert_voice({"alert_voice": "Google US English"}, session) == "Google US English"
    assert session[ALERT_VOICE_SESSION_KEY] == "Google US English"


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
    assert market_phase(datetime(2026, 7, 22, 6, 0, tzinfo=pacific)) == "Pre-Market"
    assert market_phase(datetime(2026, 7, 22, 6, 30, tzinfo=pacific)) == "Live Market"
    assert market_phase(datetime(2026, 7, 22, 12, 59, tzinfo=pacific)) == "Live Market"
    assert market_phase(datetime(2026, 7, 22, 13, 0, tzinfo=pacific)) == "After-Hours"
    assert market_phase(datetime(2026, 7, 22, 13, 5, tzinfo=pacific)) == "After-Hours"


def test_installed_english_voices_are_discovered_and_deduplicated():
    from app import normalize_discovered_voices

    voices = normalize_discovered_voices([
        {"name": "Samantha", "identifier": "com.apple.voice.compact.en-US.Samantha", "language": "en-US"},
        {"name": "Amelie", "identifier": "com.apple.voice.compact.fr-CA.Amelie", "language": "fr-CA"},
        {"name": "Samantha", "identifier": "com.apple.voice.compact.en-US.Samantha", "language": "en-US"},
        {"name": "Google UK English Female", "voiceURI": "Google UK English Female", "lang": "en-GB"},
    ])

    assert voices == [
        {"name": "Google UK English Female", "identifier": "Google UK English Female", "language": "en-GB"},
        {"name": "Samantha", "identifier": "com.apple.voice.compact.en-US.Samantha", "language": "en-US"},
    ]


def test_dropdown_contents_match_discovered_voices_with_system_first():
    from app import SYSTEM_DEFAULT_VOICE_ID, voice_options_from_discovered, voice_ids

    options = voice_options_from_discovered([
        {"name": "Daniel", "identifier": "daniel-id", "language": "en-GB"},
        {"name": "Karen", "identifier": "karen-id", "language": "en-AU"},
    ])

    assert voice_ids(options) == [SYSTEM_DEFAULT_VOICE_ID, "daniel-id", "karen-id"]
    assert options[0]["name"] == "System Default"


def test_voice_preview_uses_selected_voice_identifier():
    from app import normalize_alert_voice

    assert normalize_alert_voice("com.apple.voice.compact.en-US.Samantha") == "com.apple.voice.compact.en-US.Samantha"


def test_unavailable_voice_keeps_preference_but_falls_back_for_session():
    from app import (
        ACTIVE_VOICE_SESSION_KEY,
        ALERT_VOICE_SESSION_KEY,
        SYSTEM_DEFAULT_VOICE_ID,
        VOICE_WARNING_SESSION_KEY,
        active_voice_identifier,
        voice_options_from_discovered,
    )

    session = {ALERT_VOICE_SESSION_KEY: "missing-voice"}
    active = active_voice_identifier("missing-voice", voice_options_from_discovered([]), session)

    assert active == SYSTEM_DEFAULT_VOICE_ID
    assert session[ALERT_VOICE_SESSION_KEY] == "missing-voice"
    assert session[ACTIVE_VOICE_SESSION_KEY] == SYSTEM_DEFAULT_VOICE_ID
    assert "not available" in session[VOICE_WARNING_SESSION_KEY]

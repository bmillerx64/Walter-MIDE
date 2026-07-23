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
from mide.ui import promoted_this_scan, scanner_v2_dashboard_counts, scanner_v2_display_sections, state_sections, transition_history_markup


def test_scanner_v2_display_sections_follow_trader_workflow_order():
    records = [
        {"symbol": "READY", "candidate_status": "Entry Ready"},
        {"symbol": "WEAK", "candidate_status": "Weakening"},
        {"symbol": "WATCH", "candidate_status": "Watching"},
        {"symbol": "NEW", "candidate_status": "New"},
        {"symbol": "STRONG", "candidate_status": "Strengthening"},
        {"symbol": "REMOVED", "candidate_status": "Removed"},
    ]

    display_sections = scanner_v2_display_sections(records)

    assert [name for name, _records, _expanded in display_sections] == [
        "Entry Ready",
        "Strengthening",
        "Watch List",
        "Weak / Removed",
        "Candidates",
    ]
    assert [expanded for _name, _records, expanded in display_sections] == [True, True, True, False, False]


def test_scanner_v2_display_sections_do_not_lose_or_duplicate_symbols():
    records = [
        {"symbol": "READY", "candidate_status": "Entry Ready"},
        {"symbol": "WEAK", "candidate_status": "Weakening"},
        {"symbol": "WATCH", "candidate_status": "Watching"},
        {"symbol": "EMERGE", "candidate_status": "Emerging"},
        {"symbol": "STRONG", "candidate_status": "Strengthening"},
        {"symbol": "REMOVED", "candidate_status": "Removed"},
    ]

    rendered_symbols = [
        record["symbol"]
        for _name, section_records, _expanded in scanner_v2_display_sections(records)
        for record in section_records
    ]

    assert sorted(rendered_symbols) == sorted(record["symbol"] for record in records)
    assert len(rendered_symbols) == len(set(rendered_symbols))


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
    assert VOICE_OPTIONS == [DEFAULT_VOICE, "Samantha"]
    assert "Google US English" not in VOICE_OPTIONS
    assert "David" not in VOICE_OPTIONS


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


def test_promotion_delta_visuals_cover_watchlist_entry_and_state_advancement():
    entered = {"symbol": "NEW", "candidate_status": "Watching", "entered_watchlist": True, "advanced_state": False}
    advanced = {"symbol": "MOVE", "candidate_status": "Strengthening", "entered_watchlist": False, "advanced_state": True}
    unchanged = {"symbol": "HOLD", "candidate_status": "Strengthening", "entered_watchlist": False, "advanced_state": False}

    sections = state_sections([entered, advanced, unchanged])

    assert [record["symbol"] for record in sections["Watching"]] == ["NEW"]
    assert [record["symbol"] for record in sections["Strengthening"]] == ["MOVE", "HOLD"]
    assert promoted_this_scan(entered) is True
    assert promoted_this_scan(advanced) is True
    assert promoted_this_scan(unchanged) is False


def test_market_phase_uses_local_time_against_us_equity_hours():
    pacific = ZoneInfo("America/Los_Angeles")
    assert market_phase(datetime(2026, 7, 22, 6, 0, tzinfo=pacific)) == "Pre-Market"
    assert market_phase(datetime(2026, 7, 22, 6, 30, tzinfo=pacific)) == "Live Market"
    assert market_phase(datetime(2026, 7, 22, 12, 59, tzinfo=pacific)) == "Live Market"
    assert market_phase(datetime(2026, 7, 22, 13, 0, tzinfo=pacific)) == "After-Hours"
    assert market_phase(datetime(2026, 7, 22, 13, 5, tzinfo=pacific)) == "After-Hours"


def test_stable_voice_options_keep_system_and_samantha_without_dynamic_voices():
    from app import SYSTEM_DEFAULT_VOICE_ID, stable_voice_options, voice_ids

    options = stable_voice_options(david_available=False)

    assert voice_ids(options) == [SYSTEM_DEFAULT_VOICE_ID, "Samantha"]
    assert [option["name"] for option in options] == ["System Default", "Samantha"]


def test_david_only_displays_when_available():
    from app import stable_voice_options, voice_ids

    assert "David" not in voice_ids(stable_voice_options(david_available=False))
    assert "David" in voice_ids(stable_voice_options(david_available=True))




def test_david_availability_comes_from_browser_probe():
    from app import DAVID_AVAILABLE_SESSION_KEY, david_available_from_query

    session = {}

    assert david_available_from_query({"walter_david_available": "0"}, session) is False
    assert session[DAVID_AVAILABLE_SESSION_KEY] is False
    assert david_available_from_query({"walter_david_available": "1"}, session) is True
    assert session[DAVID_AVAILABLE_SESSION_KEY] is True

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
        stable_voice_options,
    )

    session = {ALERT_VOICE_SESSION_KEY: "missing-voice"}
    active = active_voice_identifier("missing-voice", stable_voice_options(False), session)

    assert active == SYSTEM_DEFAULT_VOICE_ID
    assert session[ALERT_VOICE_SESSION_KEY] == "missing-voice"
    assert session[ACTIVE_VOICE_SESSION_KEY] == SYSTEM_DEFAULT_VOICE_ID
    assert "not available" in session[VOICE_WARNING_SESSION_KEY]


def test_state_sections_sort_timed_states_by_newest_promotion():
    records = [
        {"symbol": "OLD", "candidate_status": "Entry Ready", "state_entered_at": "2026-07-23T14:20:00+00:00"},
        {"symbol": "NEW", "candidate_status": "Entry Ready", "state_entered_at": "2026-07-23T14:29:00+00:00"},
    ]

    sections = state_sections(records)

    assert [record["symbol"] for record in sections["Entry Ready"]] == ["NEW", "OLD"]


def test_watching_symbols_auto_sort_by_promotion_score_and_dollar_volume():
    records = [
        {"symbol": "OLDER", "candidate_status": "Watching", "state_entered_at": "2026-07-23T14:20:00+00:00", "scanner_v2_score": 99, "dollar_volume": 9_000_000},
        {"symbol": "LOWER_DOLLAR", "candidate_status": "Watching", "state_entered_at": "2026-07-23T14:30:00+00:00", "scanner_v2_score": 75, "dollar_volume": 1_000_000},
        {"symbol": "HIGHER_DOLLAR", "candidate_status": "Watching", "state_entered_at": "2026-07-23T14:30:00+00:00", "scanner_v2_score": 75, "dollar_volume": 2_000_000},
        {"symbol": "HIGHER_SCORE", "candidate_status": "Watching", "state_entered_at": "2026-07-23T14:30:00+00:00", "scanner_v2_score": 80, "dollar_volume": 500_000},
    ]

    sections = state_sections(records)

    assert [record["symbol"] for record in sections["Watching"]] == [
        "HIGHER_SCORE",
        "HIGHER_DOLLAR",
        "LOWER_DOLLAR",
        "OLDER",
    ]


def test_watching_auto_sort_is_stable_across_automatic_scans():
    records = [
        {"symbol": "AAA", "candidate_status": "Watching", "state_entered_at": "2026-07-23T14:30:00+00:00", "scanner_v2_score": 70, "dollar_volume": 1_000_000},
        {"symbol": "BBB", "candidate_status": "Watching", "state_entered_at": "2026-07-23T14:29:00+00:00", "scanner_v2_score": 90, "dollar_volume": 5_000_000},
        {"symbol": "CCC", "candidate_status": "Watching", "state_entered_at": "2026-07-23T14:30:00+00:00", "scanner_v2_score": 65, "dollar_volume": 9_000_000},
    ]

    first_scan = [record["symbol"] for record in state_sections(records)["Watching"]]
    next_scan = [record["symbol"] for record in state_sections(list(records))["Watching"]]

    assert first_scan == ["AAA", "CCC", "BBB"]
    assert next_scan == first_scan


def test_watching_sort_dropdown_no_longer_appears():
    from pathlib import Path

    app_source = Path("app.py").read_text()

    assert 'f"Sort {section_name}"' in app_source
    assert 'section_name == "Watch List"' in app_source


def test_transition_history_markup_stays_compact_under_prioritized_reasons():
    markup = transition_history_markup({
        "transition_history": [
            {"state": "Emerging", "entered_at": "2026-07-23T14:30:00+00:00"},
            {"state": "Watching", "entered_at": "2026-07-23T14:31:42+00:00"},
            {"state": "Strengthening", "entered_at": "2026-07-23T14:32:30+00:00"},
        ]
    })

    assert "transition-history" in markup
    assert "Emerging" in markup
    assert "Watch List" in markup
    assert "↓ 1m 42s" in markup
    assert "↓ 48s" in markup

from datetime import datetime, timezone

from mide.live_opportunity_feed import (
    FEED_SCHEMA_VERSION,
    FEED_TIME_BASIS,
    opportunity_feed_changes,
    update_opportunity_feed,
)


NOW = datetime(2026, 7, 27, 14, 30, 15)


def state(**overrides):
    value = {
        "participation": 80,
        "vwap": "below",
        "supertrend": False,
        "confidence": 70,
        "entry_open": False,
        "extended": False,
    }
    value.update(overrides)
    return value


def current_event(message: str = "older") -> dict:
    return {
        "time": "14:29:00",
        "time_basis": FEED_TIME_BASIS,
        "schema_version": FEED_SCHEMA_VERSION,
        "symbol": "OLD",
        "message": message,
        "color": "yellow",
        "confidence_delta": None,
    }


def test_feed_reports_only_material_transitions():
    changes = opportunity_feed_changes(
        {"DSX": state()},
        {
            "DSX": state(
                participation=92,
                vwap="above",
                supertrend=True,
                confidence=82,
                entry_open=True,
            )
        },
        NOW,
    )

    assert [event["message"] for event in changes] == [
        "Participation 80→92",
        "VWAP reclaimed",
        "SuperTrend flipped bullish",
        "Confidence +12",
        "ENTRY WINDOW OPEN",
    ]
    assert all(event["time"] == "14:30:15" for event in changes)
    assert all(event["time_basis"] == FEED_TIME_BASIS for event in changes)
    assert all(event["schema_version"] == FEED_SCHEMA_VERSION for event in changes)


def test_feed_converts_utc_scan_time_to_eastern_display_time():
    utc_scan = datetime(2026, 9, 11, 14, 30, 58, tzinfo=timezone.utc)
    changes = opportunity_feed_changes(
        {"OLD": state()},
        {},
        utc_scan,
    )

    assert changes == [
        {
            "time": "10:30:58",
            "time_basis": FEED_TIME_BASIS,
            "schema_version": FEED_SCHEMA_VERSION,
            "symbol": "OLD",
            "message": "Symbol removed from Focus",
            "color": "red",
            "confidence_delta": None,
        }
    ]


def test_feed_ignores_unchanged_states_and_small_confidence_moves():
    assert (
        opportunity_feed_changes(
            {"DSX": state(confidence=70)}, {"DSX": state(confidence=74)}, NOW
        )
        == []
    )


def test_feed_reports_negative_changes_and_focus_removal():
    changes = opportunity_feed_changes(
        {"DSX": state(vwap="above", confidence=85, entry_open=True), "OLD": state()},
        {"DSX": state(confidence=61)},
        NOW,
    )

    assert [(event["message"], event["color"]) for event in changes] == [
        ("Lost VWAP", "red"),
        ("Confidence -24", "red"),
        ("Entry Window closed", "red"),
        ("Symbol removed from Focus", "red"),
    ]


def test_feed_does_not_emit_initial_state_and_retains_ten_events():
    record = {"symbol": "DSX", "conviction_score": 70}
    snapshot, events = update_opportunity_feed(
        record and [record], {}, [current_event(str(index)) for index in range(25)], NOW
    )

    assert snapshot["DSX"]["confidence"] == 70
    assert len(events) == 10


def test_feed_reports_building_pullback_and_extension_with_requested_colors():
    changes = opportunity_feed_changes(
        {
            "DSX": state(extended=True),
            "LPRO": state(),
            "RISK": state(),
        },
        {
            "DSX": state(extended=False, pullback=True),
            "LPRO": state(building=True),
            "RISK": state(extended=True),
        },
        NOW,
    )

    assert [
        (event["symbol"], event["message"], event["color"]) for event in changes
    ] == [
        ("DSX", "Pullback", "yellow"),
        ("LPRO", "Entered BUILDING", "yellow"),
        ("RISK", "Too extended", "red"),
    ]


def test_new_events_are_newest_first():
    _, events = update_opportunity_feed(
        [],
        {"OLD": state()},
        [current_event()],
        NOW,
    )

    assert [event["message"] for event in events] == [
        "Symbol removed from Focus",
        "older",
    ]


def test_feed_drops_legacy_rows_with_ambiguous_pre_gs438_clock_basis():
    legacy_utc_row = {
        "time": "14:43:24",
        "symbol": "CRMT",
        "message": "Symbol removed from Focus",
        "color": "red",
        "confidence_delta": None,
    }
    valid = current_event("valid Eastern row")

    _, events = update_opportunity_feed([], {}, [legacy_utc_row, valid], NOW)

    assert events == [valid]

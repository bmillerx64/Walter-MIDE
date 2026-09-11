from datetime import datetime, timezone

from mide.live_opportunity_feed import (
    FEED_SCHEMA_VERSION,
    FEED_TIME_BASIS,
    _event,
    _event_priority,
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


def test_feed_reports_structural_transitions_without_confidence_chatter():
    changes = opportunity_feed_changes(
        {"DSX": state()},
        {
            "DSX": state(
                participation=92,
                vwap="above",
                supertrend=True,
                confidence=90,
                entry_open=True,
            )
        },
        NOW,
    )

    assert [event["message"] for event in changes] == [
        "Participation 80→92",
        "VWAP reclaimed",
        "SuperTrend flipped bullish",
        "ENTRY WINDOW OPEN",
    ]
    assert all(event["time"] == "14:30:15" for event in changes)
    assert all(event["time_basis"] == FEED_TIME_BASIS for event in changes)
    assert all(event["schema_version"] == FEED_SCHEMA_VERSION for event in changes)


def test_feed_converts_utc_scan_time_to_eastern_for_entry_window_focus_loss():
    utc_scan = datetime(2026, 9, 11, 14, 30, 58, tzinfo=timezone.utc)
    changes = opportunity_feed_changes(
        {"OLD": state(entry_open=True)},
        {},
        utc_scan,
    )

    assert changes == [
        {
            "time": "10:30:58",
            "time_basis": FEED_TIME_BASIS,
            "schema_version": FEED_SCHEMA_VERSION,
            "symbol": "OLD",
            "message": "ENTRY WINDOW LEFT FOCUS",
            "color": "red",
            "confidence_delta": None,
        }
    ]


def test_routine_focus_rotation_is_not_a_feed_event():
    assert opportunity_feed_changes(
        {"AIXC": state(), "FTFT": state(building=True)},
        {},
        NOW,
    ) == []


def test_feed_ignores_unchanged_states_and_small_confidence_moves():
    assert (
        opportunity_feed_changes(
            {"DSX": state(confidence=70)}, {"DSX": state(confidence=84)}, NOW
        )
        == []
    )


def test_feed_reports_large_standalone_confidence_move_only():
    positive = opportunity_feed_changes(
        {"DSX": state(confidence=60)}, {"DSX": state(confidence=76)}, NOW
    )
    negative = opportunity_feed_changes(
        {"DSX": state(confidence=80)}, {"DSX": state(confidence=62)}, NOW
    )

    assert [(event["message"], event["color"]) for event in positive] == [
        ("Confidence +16", "green")
    ]
    assert [(event["message"], event["color"]) for event in negative] == [
        ("Confidence -18", "red")
    ]


def test_feed_structural_change_suppresses_even_large_confidence_move_and_focus_housekeeping():
    changes = opportunity_feed_changes(
        {"DSX": state(vwap="above", confidence=85, entry_open=True), "OLD": state()},
        {"DSX": state(confidence=61)},
        NOW,
    )

    assert [(event["message"], event["color"]) for event in changes] == [
        ("Lost VWAP", "red"),
        ("Entry Window closed", "red"),
    ]


def test_same_scan_feed_priority_keeps_entry_window_focus_loss_with_risk_events():
    changes = [
        _event("OLD", "ENTRY WINDOW LEFT FOCUS", "red", NOW),
        _event("DSX", "Confidence +20", "green", NOW, 20),
        _event("DSX", "Entered BUILDING", "yellow", NOW),
        _event("DSX", "VWAP reclaimed", "green", NOW),
        _event("DSX", "Too extended", "red", NOW),
        _event("DSX", "ENTRY WINDOW OPEN", "green", NOW),
    ]

    ordered = sorted(changes, key=_event_priority, reverse=True)
    assert [event["message"] for event in ordered] == [
        "ENTRY WINDOW OPEN",
        "ENTRY WINDOW LEFT FOCUS",
        "Too extended",
        "VWAP reclaimed",
        "Entered BUILDING",
        "Confidence +20",
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


def test_routine_focus_rotation_does_not_displace_existing_feed_history():
    _, events = update_opportunity_feed(
        [],
        {"OLD": state()},
        [current_event()],
        NOW,
    )

    assert [event["message"] for event in events] == ["older"]


def test_feed_drops_rows_from_older_presentation_schemas():
    legacy_utc_row = {
        "time": "14:43:24",
        "symbol": "CRMT",
        "message": "Symbol removed from Focus",
        "color": "red",
        "confidence_delta": None,
    }
    prior_schema_row = {
        "time": "10:43:24",
        "time_basis": FEED_TIME_BASIS,
        "schema_version": FEED_SCHEMA_VERSION - 1,
        "symbol": "BDRX",
        "message": "Symbol removed from Focus",
        "color": "red",
        "confidence_delta": None,
    }
    valid = current_event("valid current row")

    _, events = update_opportunity_feed(
        [], {}, [legacy_utc_row, prior_schema_row, valid], NOW
    )

    assert events == [valid]

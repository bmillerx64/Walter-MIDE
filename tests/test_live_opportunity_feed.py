from datetime import datetime

from mide.live_opportunity_feed import opportunity_feed_changes, update_opportunity_feed


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
    snapshot, events = update_opportunity_feed(record and [record], {}, [{}] * 25, NOW)

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
        [{"message": "older"}],
        NOW,
    )

    assert [event["message"] for event in events] == [
        "Symbol removed from Focus",
        "older",
    ]

from copy import deepcopy

from mide.escalation import (
    WATCH_CLOSELY,
    escalation_alert_phrase,
    escalation_state_changes,
)


def first_print(**changes):
    record = {
        "symbol": "BTCT",
        "candidate_status": "Watching",
        "qualified_for_entry": False,
        "vwap_relation": "above",
        "vwap_distance_pct": 0.6,
        "supertrend_flip": True,
        "supertrend_bullish": True,
        "participation_surge_score": 66,
        "volume_acceleration": 2.4,
        "rvol_proxy": 3.5,
        "pct_change": 12.0,
        "price_change_10m_pct": 5.0,
        "headline": "",
    }
    record.update(changes)
    return record


def test_first_print_ignition_emits_dedupable_escalation_event():
    changes = escalation_state_changes([first_print()])
    assert changes == [
        {
            "symbol": "BTCT",
            "from": "New",
            "to": WATCH_CLOSELY,
            "event": "first_print_ignition",
        }
    ]
    signature = "|".join(
        f"{item['symbol']}:{item['from']}->{item['to']}" for item in changes
    )
    assert signature == "BTCT:New->Watch Closely"


def test_first_print_ignition_is_audible_through_existing_phrase_path():
    phrase = escalation_alert_phrase([first_print()])
    assert "BTCT" in phrase
    assert WATCH_CLOSELY in phrase


def test_non_ignition_first_print_does_not_create_event():
    record = first_print(
        supertrend_flip=False,
        supertrend_bullish=True,
        participation_surge_score=40,
        volume_acceleration=1.2,
        rvol_proxy=1.4,
    )
    assert escalation_state_changes([record]) == []


def test_prior_scan_transition_remains_owned_by_existing_transition_logic():
    record = first_print(
        opportunity_pulse_previous={
            "symbol": "BTCT",
            "candidate_status": "Watching",
            "vwap_relation": "above",
            "vwap_distance_pct": 0.8,
            "supertrend_bullish": True,
            "conviction_score": 40,
            "participation_surge_score": 55,
            "expansion_quality": 50,
            "volume_acceleration": 1.8,
            "rvol_proxy": 2.5,
        },
        conviction_score=47,
        participation_surge_score=64,
        expansion_quality=58,
    )
    changes = escalation_state_changes([record])
    assert all(item.get("event") != "first_print_ignition" for item in changes)


def test_overextended_first_print_does_not_create_watch_event():
    assert escalation_state_changes([first_print(vwap_distance_pct=6.0)]) == []


def test_alert_observer_does_not_mutate_records():
    record = first_print()
    before = deepcopy(record)
    escalation_state_changes([record])
    escalation_alert_phrase([record])
    assert record == before

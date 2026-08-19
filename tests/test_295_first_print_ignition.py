from copy import deepcopy

from mide.escalation import (
    ENTRY_WINDOW_OPEN,
    MONITOR,
    TOO_EXTENDED,
    WATCH_CLOSELY,
    escalation_snapshot,
    escalation_state,
    first_print_ignition,
)


def runner(**changes):
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


def test_first_print_no_news_ignition_promotes_human_review():
    record = runner()
    assert first_print_ignition(record)["promoted"] is True
    assert escalation_state(record) == WATCH_CLOSELY


def test_first_print_requires_actual_supertrend_flip_not_only_bullish_state():
    record = runner(supertrend_flip=False, supertrend_bullish=True)
    assert first_print_ignition(record)["promoted"] is False
    assert escalation_state(record) == MONITOR


def test_first_print_requires_vwap_support():
    record = runner(vwap_relation="below", vwap_distance_pct=-0.5)
    assert first_print_ignition(record)["promoted"] is False
    assert escalation_state(record) == MONITOR


def test_first_print_requires_hot_participation():
    record = runner(
        participation_surge_score=40,
        volume_acceleration=1.2,
        rvol_proxy=1.4,
    )
    assert first_print_ignition(record)["promoted"] is False
    assert escalation_state(record) == MONITOR


def test_first_print_requires_real_momentum_or_breakout():
    record = runner(pct_change=4, price_change_10m_pct=1.0)
    assert first_print_ignition(record)["promoted"] is False
    assert escalation_state(record) == MONITOR


def test_prior_pulse_stays_owned_by_gs293_not_first_print_path():
    record = runner(opportunity_pulse_previous={"conviction_score": 40})
    assert first_print_ignition(record)["promoted"] is False


def test_overextension_hard_stop_still_overrides_ignition():
    record = runner(vwap_distance_pct=6.0)
    assert escalation_state(record) == TOO_EXTENDED


def test_existing_entry_ready_state_still_wins():
    record = runner(qualified_for_entry=True)
    assert escalation_state(record) == ENTRY_WINDOW_OPEN


def test_snapshot_exposes_first_print_evidence():
    snapshot = escalation_snapshot(runner())
    assert snapshot["state"] == WATCH_CLOSELY
    assert snapshot["first_print_ignition"]["promoted"] is True
    assert snapshot["first_print_ignition"]["supertrend_flip"] is True


def test_first_print_observer_never_mutates_candidate():
    record = runner()
    before = deepcopy(record)
    first_print_ignition(record)
    escalation_state(record)
    escalation_snapshot(record)
    assert record == before

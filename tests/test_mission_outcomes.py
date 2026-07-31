from copy import deepcopy
from datetime import datetime, timedelta, timezone

from mide.mission_outcomes import MissionOutcomeStore


START = datetime(2026, 7, 31, 14, 30, tzinfo=timezone.utc)


def candidate(**updates):
    value = {
        "symbol": "WALT", "candidate_id": "WALT", "mission_rank": 2,
        "price": 10, "conviction_score": 81, "participation_score": 72,
        "expansion_score": 68, "candidate_status": "Watching",
        "vwap_relation": "above", "supertrend_bullish": True,
        "volume": 1000, "rvol": 3.2, "catalyst_evidence": {"wire": "Reuters"},
        "decision_explanation": {"decision_narrative": "ranked from recorded evidence"},
        "profit_target": 11, "stop_level": 9,
    }
    value.update(updates)
    return value


def test_one_identity_per_appearance_and_no_rerun_duplicate(tmp_path):
    store = MissionOutcomeStore(tmp_path / "outcomes.json")
    store.process_scan([candidate()], timestamp=START)
    store.process_scan([candidate()], timestamp=START)
    records = store.all()
    assert len(records) == 1
    assert records[0]["outcome_id"] == "2026-07-31|WALT|1"
    assert len(records[0]["observations"]) == 1


def test_intervals_measure_change_excursions_and_states(tmp_path):
    store = MissionOutcomeStore(tmp_path / "outcomes.json")
    store.process_scan([candidate()], timestamp=START)
    store.process_scan([candidate(price=11, high=12, low=9.5, mission_rank=1, volume=2000)], timestamp=START + timedelta(minutes=2))
    measurement = store.all()[0]["measurements"]["2m"]
    assert measurement["percentage_change"] == 10
    assert measurement["maximum_favorable_excursion"] == 20
    assert measurement["maximum_adverse_excursion"] == -5
    assert measurement["volume"] == 2000
    assert measurement["walter_rank_change"] == "upgraded"


def test_pre_entry_movement_is_not_a_trade_outcome(tmp_path):
    store = MissionOutcomeStore(tmp_path / "outcomes.json")
    store.process_scan([candidate()], timestamp=START)
    store.process_scan([candidate(price=12, high=12)], timestamp=START + timedelta(minutes=2))
    outcome = store.all()[0]
    assert outcome["measurements"]["2m"]["percentage_change"] == 20
    assert not outcome["profit_target_reached"]
    assert not outcome["stop_level_reached"]


def test_entry_ready_transition_starts_trade_evaluation(tmp_path):
    store = MissionOutcomeStore(tmp_path / "outcomes.json")
    store.process_scan([candidate(price=8, low=8)], timestamp=START)
    store.process_scan([candidate(candidate_status="Entry Ready", price=10)], timestamp=START + timedelta(minutes=1))
    store.process_scan([candidate(candidate_status="Entry Ready", price=11, high=11)], timestamp=START + timedelta(minutes=2))
    outcome = store.all()[0]
    assert outcome["became_entry_ready"]
    assert outcome["entry_ready_price"] == 10
    assert outcome["profit_target_reached"]
    assert not outcome["stop_level_reached"]


def test_removed_candidates_and_restarts_preserve_history(tmp_path):
    path = tmp_path / "outcomes.json"
    MissionOutcomeStore(path).process_scan([candidate()], timestamp=START)
    MissionOutcomeStore(path).process_scan([], timestamp=START + timedelta(minutes=3))
    outcome = MissionOutcomeStore(path).all()[0]
    assert outcome["removed_before_entry_readiness"]
    assert outcome["never_became_entry_ready"]
    assert outcome["completed"]


def test_tracking_cannot_mutate_candidate_decisions(tmp_path):
    source = candidate(ranking_history=[{"rank": 2}])
    original = deepcopy(source)
    MissionOutcomeStore(tmp_path / "outcomes.json").process_scan([source], timestamp=START)
    assert source == original

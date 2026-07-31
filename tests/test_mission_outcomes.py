from copy import deepcopy
from datetime import datetime, timedelta, timezone

from mide.mission_outcomes import MissionOutcomeStore, OutcomeAnalyticsEngine


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


def test_completed_outcome_has_excursions_timing_classification_and_attribution(tmp_path):
    store = MissionOutcomeStore(tmp_path / "outcomes.json")
    store.process_scan([candidate(candidate_status="Entry Window", mission_rank=1)], timestamp=START)
    store.process_scan([candidate(candidate_status="Entry Window", price=10.5, high=11.2, low=9.7, mission_rank=1)], timestamp=START + timedelta(minutes=4))
    store.process_scan([], timestamp=START + timedelta(minutes=5))
    outcome = store.all()[0]
    assert outcome["maximum_favorable_excursion"] == 12
    assert outcome["maximum_adverse_excursion"] == -3
    assert outcome["time_to_entry_ready"] == 0
    assert outcome["time_to_peak"] == 4
    assert outcome["closing_outcome"]["percentage_change"] == 5
    assert outcome["classification"] == "Excellent"
    assert set(outcome["component_attribution"]) == {
        "Catalyst Assessment", "Participation Assessment", "Expansion Assessment",
        "Conviction", "Entry Readiness", "Mission Ranking",
    }


def test_never_triggered_is_objectively_classified(tmp_path):
    store = MissionOutcomeStore(tmp_path / "outcomes.json")
    store.process_scan([candidate(price=10)], timestamp=START)
    store.process_scan([], timestamp=START + timedelta(minutes=1))
    assert store.all()[0]["classification"] == "Never Triggered"


def test_historical_summaries_scorecards_ranking_and_readiness():
    def completed(symbol, rank, state, change, classification, day="2026-07-31"):
        success = classification in {"Excellent", "Good"}
        predictions = {
            name: {"predicted_success": rank == 1, "actual_success": success, "correct": (rank == 1) == success}
            for name in ("Catalyst Assessment", "Participation Assessment", "Expansion Assessment", "Conviction", "Entry Readiness", "Mission Ranking")
        }
        return {"completed": True, "classification": classification, "symbol": symbol,
                "session_date": day, "initial_rank": rank, "initial_readiness_state": state,
                "became_entry_ready": state == "Entry Window", "closing_outcome": {"percentage_change": change},
                "maximum_favorable_excursion": max(change, 0), "maximum_adverse_excursion": min(change, 0),
                "component_attribution": predictions}

    engine = OutcomeAnalyticsEngine([
        completed("ONE", 1, "Entry Window", 8, "Good"),
        completed("TWO", 2, "Early", 3, "Good"),
        completed("THREE", 3, "Watch", -2, "Weak"),
    ])
    assert engine.ranking_validation()["accuracy"] == 100
    assert engine.ranking_validation()["rank_2_outperformed_rank_3"] == 1
    assert engine.readiness_validation()["entry_window_superior"]
    daily = engine.daily_summary("2026-07-31")
    assert daily["total_mission_candidates"] == 3
    assert daily["winners"] == 2
    assert daily["losers"] == 1
    assert daily["average_gain"] == 5.5
    assert engine.component_scorecards()["Mission Ranking"]["observations"] == 3
    assert engine.weekly_summary()["subsystems"]["Mission Ranking"]["performance"] == "stable"


def test_analytics_owns_copies_and_cannot_change_runtime_records():
    records = [{"completed": True, "classification": "Good", "session_date": "2026-07-31",
                "closing_outcome": {"percentage_change": 4}, "component_attribution": {}}]
    original = deepcopy(records)
    engine = OutcomeAnalyticsEngine(records)
    engine.records[0]["closing_outcome"]["percentage_change"] = -99
    assert records == original

import json
from datetime import datetime, timezone
from types import SimpleNamespace

from mide.decision_time_evidence import verify_decision_time_evidence
from mide.flight_recorder import FlightRecorder
from mide.flight_recorder_replay_api import replay_from_recorder


def test_record_scan_persists_replayable_decision_time_evidence(tmp_path):
    path = tmp_path / "flight.jsonl"
    recorder = FlightRecorder(path=path)
    settings = SimpleNamespace(
        min_price=0.02,
        max_price=5.0,
        min_pct_change=0.0,
        min_day_volume=1,
        max_free_float=100_000_000,
    )
    snapshot = {
        "latestTrade": {"p": 1.50},
        "latestQuote": {"bp": 1.49, "ap": 1.51},
        "dailyBar": {"c": 1.50, "v": 1000},
        "prevDailyBar": {"c": 1.00},
    }
    record = {
        "symbol": "ABC",
        "price": 1.50,
        "participation_gate": {"passed": True},
        "structure_gate": {"passed": True},
        "qualified_for_ranking": True,
        "qualified_for_watch": True,
        "candidate_status": "WATCH",
        "status": "WATCH",
    }

    scan = recorder.record_scan(
        seeds=["ABC"],
        discovery_reasons={"ABC": ["test seed"]},
        snapshots={"ABC": snapshot},
        candidates=[{"symbol": "ABC"}],
        analyzed=[{"symbol": "ABC"}],
        records=[record],
        settings=settings,
        timestamp=datetime(2026, 8, 13, 2, 55, tzinfo=timezone.utc),
    )

    persisted = json.loads(path.read_text().strip())
    evidence = persisted["symbols"][0]["decision_time_evidence"]

    assert persisted == scan
    assert verify_decision_time_evidence(evidence)
    assert evidence["price"] == 1.50

    replay = replay_from_recorder(recorder, scan_id=scan["scan_id"], symbol="ABC")
    assert replay["integrity_verified"] is True
    assert replay["decision_inputs"]["price"] == 1.50
    assert replay["replay_state"] == "WATCH"


def test_record_scan_keeps_paths_without_final_records_legacy_compatible(tmp_path):
    recorder = FlightRecorder(path=tmp_path / "flight.jsonl")
    settings = SimpleNamespace(
        min_price=0.02,
        max_price=5.0,
        min_pct_change=0.0,
        min_day_volume=1,
        max_free_float=100_000_000,
    )

    scan = recorder.record_scan(
        seeds=["MISS"],
        discovery_reasons={"MISS": ["test seed"]},
        snapshots={},
        candidates=[],
        analyzed=[],
        records=[],
        settings=settings,
        timestamp=datetime(2026, 8, 13, 2, 56, tzinfo=timezone.utc),
    )

    assert "decision_time_evidence" not in scan["symbols"][0]

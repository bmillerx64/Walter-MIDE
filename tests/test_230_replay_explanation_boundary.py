from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from mide.flight_recorder import FlightRecorder
from mide.flight_recorder_replay_api import explain_from_recorder
from mide.replay_explanation import explain_replay


def test_replay_explanation_is_bounded_to_immutable_evidence(tmp_path):
    recorder = FlightRecorder(path=tmp_path / "flight.jsonl")
    settings = SimpleNamespace(
        min_price=0.02,
        max_price=5.0,
        min_pct_change=0.0,
        min_day_volume=1,
        max_free_float=100_000_000,
    )
    record = {
        "symbol": "ABC",
        "price": 1.50,
        "participation_gate": {"passed": True},
        "structure_gate": {"passed": True},
        "qualified_for_ranking": True,
        "qualified_for_watch": True,
        "qualified_for_entry": False,
        "candidate_status": "WATCH",
        "status": "WATCH",
        "rejection_reason": "waiting for trigger confirmation",
    }
    scan = recorder.record_scan(
        seeds=["ABC"],
        discovery_reasons={"ABC": ["test seed"]},
        snapshots={"ABC": {"latestTrade": {"p": 1.50}}},
        candidates=[{"symbol": "ABC"}],
        analyzed=[{"symbol": "ABC"}],
        records=[record],
        settings=settings,
        timestamp=datetime(2026, 8, 13, 3, 10, tzinfo=timezone.utc),
    )

    explanation = explain_from_recorder(recorder, scan_id=scan["scan_id"], symbol="ABC")

    assert explanation["integrity_verified"] is True
    assert explanation["replay_state"] == "WATCH"
    assert explanation["decision_inputs"]["price"] == 1.50
    assert "waiting for trigger confirmation" in explanation["explanation"]
    assert explanation["evidence_source"] == "immutable decision_time_evidence"


def test_replay_explanation_rejects_unverified_input():
    with pytest.raises(ValueError, match="integrity-verified"):
        explain_replay({"symbol": "ABC", "replay_state": "WATCH"})

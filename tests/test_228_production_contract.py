import json
from types import SimpleNamespace

from mide.flight_recorder_replay_api import replay_from_recorder
from mide.flight_recorder import FlightRecorder
from mide.flight_recorder_writer import persist_replayable_scan


def test_228_written_scan_is_immediately_replayable(tmp_path):
    path = tmp_path / "flight.jsonl"
    writer_target = SimpleNamespace(path=path)
    scan = {
        "scan_id": "scan-228",
        "timestamp": "2026-08-13T02:00:00+00:00",
        "symbols": [{"symbol": "ABC", "events": []}],
    }
    records = [{
        "symbol": "ABC",
        "price": 1.75,
        "participation_gate": {"passed": True},
        "structure_gate": {"passed": True},
        "qualified_for_watch": True,
        "candidate_status": "WATCH",
    }]
    persist_replayable_scan(writer_target, scan, records)

    replay = replay_from_recorder(
        FlightRecorder(path=path), scan_id="scan-228", symbol="ABC"
    )
    assert replay["integrity_verified"] is True
    assert replay["decision_inputs"]["price"] == 1.75
    assert replay["replay_state"] == "WATCH"

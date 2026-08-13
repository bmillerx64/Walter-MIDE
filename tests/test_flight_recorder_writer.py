import json
from types import SimpleNamespace

from mide.decision_time_evidence import verify_decision_time_evidence
from mide.flight_recorder_writer import persist_replayable_scan


def test_writer_persists_replayable_scan_without_mutating_input(tmp_path):
    recorder = SimpleNamespace(path=tmp_path / "flight.jsonl")
    scan = {
        "scan_id": "scan-1",
        "timestamp": "2026-08-13T02:00:00+00:00",
        "symbols": [{"symbol": "ABC", "evidence": {"existing": True}}],
    }
    records = [{
        "symbol": "ABC",
        "price": 1.5,
        "participation_gate": {"passed": True},
        "structure_gate": {"passed": True},
        "qualified_for_watch": True,
        "candidate_status": "WATCH",
    }]
    written = persist_replayable_scan(recorder, scan, records)
    persisted = json.loads(recorder.path.read_text().strip())

    assert "decision_time_evidence" not in scan["symbols"][0]
    assert persisted == written
    assert persisted["symbols"][0]["evidence"] == {"existing": True}
    assert verify_decision_time_evidence(
        persisted["symbols"][0]["decision_time_evidence"]
    )

import json

import pytest

from mide.decision_time_evidence import capture_decision_time_evidence
from mide.flight_recorder import FlightRecorder
from mide.flight_recorder_replay_api import (
    replay_from_recorder,
    replay_latest_from_recorder,
)
from mide.flight_replay import ReplayNotAvailable


def _scan(scan_id, symbol, price):
    evidence = capture_decision_time_evidence(
        {
            "symbol": symbol,
            "price": price,
            "participation_gate": {"passed": True},
            "structure_gate": {"passed": True},
            "qualified_for_watch": True,
            "candidate_status": "WATCH",
        },
        scan_id=scan_id,
        scan_timestamp="2026-08-13T01:00:00+00:00",
    )
    return {"scan_id": scan_id, "symbols": [
        {"symbol": symbol, "decision_time_evidence": evidence}
    ]}


def test_replay_reads_persisted_jsonl(tmp_path):
    path = tmp_path / "flight.jsonl"
    scans = [_scan("one", "ABC", 1.0), _scan("two", "ABC", 2.0)]
    path.write_text("".join(json.dumps(scan) + "\n" for scan in scans))
    recorder = FlightRecorder(path=path)

    assert replay_from_recorder(recorder, scan_id="one", symbol="ABC")["decision_inputs"]["price"] == 1.0
    assert replay_latest_from_recorder(recorder, "ABC")["decision_inputs"]["price"] == 2.0


def test_missing_scan_fails_explicitly(tmp_path):
    recorder = FlightRecorder(path=tmp_path / "flight.jsonl")
    with pytest.raises(ReplayNotAvailable, match="not found"):
        replay_from_recorder(recorder, scan_id="missing", symbol="ABC")

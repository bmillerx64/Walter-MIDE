import json

from mide.flight_recorder import FlightRecorder
from mide.replay_export import build_replay_export


def test_replay_export_preserves_recorder_and_adds_audit(tmp_path):
    path = tmp_path / "flight.jsonl"
    path.write_text(json.dumps({"scan_id": "legacy", "symbols": [{"symbol": "OLD"}]}) + "\n")
    export = build_replay_export(FlightRecorder(path=path))
    assert export["format"] == "walter-flight-replay-v1"
    assert export["scan_count"] == 1
    assert export["flight_recorder"][0]["scan_id"] == "legacy"
    assert export["audits"][0]["legacy_without_evidence"] == 1

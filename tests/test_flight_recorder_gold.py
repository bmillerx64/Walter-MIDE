from mide.decision_time_evidence import verify_decision_time_evidence
from mide.flight_recorder_gold import make_paths_replayable


def test_only_analyzed_records_receive_replay_evidence():
    paths = [{"symbol": "ABC"}, {"symbol": "XYZ"}]
    records = [{
        "symbol": "ABC",
        "price": 1.2,
        "participation_gate": {"passed": True},
        "structure_gate": {"passed": False},
    }]
    result = make_paths_replayable(
        paths,
        records,
        scan_id="scan-1",
        scan_timestamp="2026-08-13T01:00:00+00:00",
        data_mode="Live Webull",
    )
    assert verify_decision_time_evidence(result[0]["decision_time_evidence"])
    assert "decision_time_evidence" not in result[1]
    assert "decision_time_evidence" not in paths[0]

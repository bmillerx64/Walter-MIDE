from mide.decision_time_evidence import verify_decision_time_evidence
from mide.flight_recorder_persistence import prepare_replayable_paths


def test_prepare_replayable_paths_is_additive_and_non_mutating():
    paths = [{"symbol": "ABC", "stage_reached": "Structure Gate", "evidence": {"old": True}}]
    records = [{
        "symbol": "ABC",
        "price": 1.25,
        "participation_gate": {"passed": True},
        "structure_gate": {"passed": True},
        "qualified_for_watch": True,
        "candidate_status": "WATCH",
    }]
    result = prepare_replayable_paths(
        paths,
        records,
        scan_id="scan-1",
        scan_timestamp="2026-08-13T02:00:00+00:00",
    )
    assert result[0]["evidence"] == {"old": True}
    assert "decision_time_evidence" not in paths[0]
    assert verify_decision_time_evidence(result[0]["decision_time_evidence"])


def test_path_without_final_record_remains_legacy_compatible():
    paths = [{"symbol": "MISS", "events": []}]
    result = prepare_replayable_paths(
        paths,
        [],
        scan_id="scan-1",
        scan_timestamp="2026-08-13T02:00:00+00:00",
    )
    assert result == paths

from copy import deepcopy

from mide.decision_time_evidence import capture_decision_time_evidence
from mide.flight_replay import replay_recorded_symbol


def test_replay_does_not_mutate_persisted_scan_payload():
    evidence = capture_decision_time_evidence(
        {"symbol": "ABC", "participation_gate": {"passed": True}, "structure_gate": {"passed": True}},
        scan_id="s1",
        scan_timestamp="2026-08-13T01:00:00+00:00",
    )
    scan = {"scan_id": "s1", "symbols": [{"symbol": "ABC", "decision_time_evidence": evidence}]}
    before = deepcopy(scan)
    replay_recorded_symbol(scan, "ABC")
    assert scan == before

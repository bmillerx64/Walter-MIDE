from mide.decision_time_evidence import verify_decision_time_evidence
from mide.flight_recorder_evidence import attach_decision_time_evidence


def test_attach_evidence_is_hash_protected_and_non_mutating():
    path = {"symbol": "ABC", "stage_reached": "Structure Gate"}
    record = {
        "symbol": "ABC",
        "price": 1.42,
        "participation_gate": {"passed": True},
        "structure_gate": {"passed": True},
        "qualified_for_watch": True,
    }
    enriched = attach_decision_time_evidence(
        path,
        record,
        scan_id="scan-1",
        scan_timestamp="2026-08-13T01:00:00+00:00",
        data_mode="Live Webull",
    )
    assert "decision_time_evidence" not in path
    assert enriched["symbol"] == "ABC"
    assert verify_decision_time_evidence(enriched["decision_time_evidence"])


def test_no_record_does_not_invent_decision_evidence():
    path = {"symbol": "ABC"}
    assert attach_decision_time_evidence(
        path,
        None,
        scan_id="scan-1",
        scan_timestamp="2026-08-13T01:00:00+00:00",
    ) == path

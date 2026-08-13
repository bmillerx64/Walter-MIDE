from mide.decision_time_evidence import capture_decision_time_evidence
from mide.flight_replay import replay_recorded_symbol


def test_replay_preserves_historical_value_after_live_record_changes():
    live_record = {
        "symbol": "ABC",
        "price": 1.00,
        "participation_gate": {"passed": True},
        "structure_gate": {"passed": True},
        "qualified_for_watch": True,
        "candidate_status": "WATCH",
    }
    frozen = capture_decision_time_evidence(
        live_record,
        scan_id="scan-1",
        scan_timestamp="2026-08-13T01:00:00+00:00",
    )
    scan = {"scan_id": "scan-1", "symbols": [
        {"symbol": "ABC", "decision_time_evidence": frozen}
    ]}

    # Simulate the live object moving on after the recorder has frozen its evidence.
    live_record["price"] = 5.00
    live_record["qualified_for_entry"] = True
    live_record["candidate_status"] = "ENTRY READY"

    replay = replay_recorded_symbol(scan, "ABC")
    assert replay["decision_inputs"]["price"] == 1.00
    assert replay["replay_state"] == "WATCH"
    assert replay["recorded_status"] == "WATCH"

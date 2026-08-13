from datetime import datetime, timezone

from mide.decision_time_evidence import (
    capture_decision_time_evidence,
    verify_decision_time_evidence,
)


def sample_record():
    return {
        "symbol": "WALT",
        "price": 1.25,
        "vwap_value": 1.20,
        "vwap_distance_pct": 4.1667,
        "volume_pace_ratio": 2.4,
        "supertrend_bullish": True,
        "timeframes": {"1m": {"supertrend": True}},
        "participation_gate": {"passed": True, "checks": []},
        "structure_gate": {"passed": True, "checks": []},
        "trigger_diagnostics": {"trigger": False, "checks": [{"condition": "fresh flip", "passed": False}]},
        "candidate_status": "EARLY",
        "qualified_for_watch": True,
        "qualified_for_entry": False,
    }


def test_capture_is_detached_from_live_record_mutation():
    record = sample_record()
    evidence = capture_decision_time_evidence(
        record,
        scan_id="scan-1",
        scan_timestamp=datetime(2026, 8, 12, 20, 0, tzinfo=timezone.utc),
        data_mode="Live Webull",
    )
    record["price"] = 9.99
    record["timeframes"]["1m"]["supertrend"] = False
    assert evidence["price"] == 1.25
    assert evidence["timeframes"]["1m"]["supertrend"] is True
    assert verify_decision_time_evidence(evidence)


def test_digest_detects_retrospective_evidence_changes():
    evidence = capture_decision_time_evidence(
        sample_record(), scan_id="scan-2", scan_timestamp="2026-08-12T20:00:00+00:00"
    )
    evidence["price"] = 2.00
    assert not verify_decision_time_evidence(evidence)


def test_snapshot_preserves_decision_and_blocker_state():
    evidence = capture_decision_time_evidence(
        sample_record(), scan_id="scan-3", scan_timestamp="2026-08-12T20:00:00+00:00"
    )
    assert evidence["candidate_status"] == "EARLY"
    assert evidence["qualified_for_watch"] is True
    assert evidence["qualified_for_entry"] is False
    assert evidence["trigger_result"] is False

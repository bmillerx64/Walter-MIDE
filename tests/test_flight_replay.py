from copy import deepcopy

import pytest

from mide.decision_replay import InvalidDecisionEvidence
from mide.decision_time_evidence import capture_decision_time_evidence
from mide.flight_replay import ReplayNotAvailable, replay_recorded_symbol, replay_scan


def _evidence(symbol="TEST", *, entry=False):
    return capture_decision_time_evidence(
        {
            "symbol": symbol,
            "price": 1.25,
            "participation_gate": {"passed": True},
            "structure_gate": {"passed": True},
            "qualified_for_watch": True,
            "qualified_for_entry": entry,
            "qualified_for_alert": entry,
            "candidate_status": "ENTRY READY" if entry else "WATCH",
            "trigger_diagnostics": {"trigger": "GO" if entry else "WAIT", "checks": []},
        },
        scan_id="scan-1",
        scan_timestamp="2026-08-13T01:00:00+00:00",
        data_mode="Live Webull",
    )


def test_replay_recorded_symbol_uses_frozen_evidence():
    scan = {"scan_id": "scan-1", "symbols": [
        {"symbol": "TEST", "decision_time_evidence": _evidence()}
    ]}
    result = replay_recorded_symbol(scan, "test")
    assert result["symbol"] == "TEST"
    assert result["replay_state"] == "WATCH"
    assert result["integrity_verified"] is True


def test_replay_scan_replays_all_evidenced_symbols():
    scan = {"scan_id": "scan-1", "symbols": [
        {"symbol": "AAA", "decision_time_evidence": _evidence("AAA")},
        {"symbol": "BBB", "decision_time_evidence": _evidence("BBB", entry=True)},
    ]}
    assert [item["replay_state"] for item in replay_scan(scan)] == ["WATCH", "ENTRY_READY"]


def test_replay_rejects_mutated_recorder_evidence():
    evidence = _evidence()
    evidence["price"] = 99
    scan = {"scan_id": "scan-1", "symbols": [
        {"symbol": "TEST", "decision_time_evidence": evidence}
    ]}
    with pytest.raises(InvalidDecisionEvidence):
        replay_recorded_symbol(scan, "TEST")


def test_old_scan_without_immutable_evidence_fails_explicitly():
    scan = {"scan_id": "old-scan", "symbols": [{"symbol": "TEST", "evidence": {}}]}
    with pytest.raises(ReplayNotAvailable, match="predates"):
        replay_recorded_symbol(scan, "TEST")

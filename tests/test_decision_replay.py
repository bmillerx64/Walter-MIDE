import pytest

from mide.decision_replay import InvalidDecisionEvidence, replay_decision
from mide.decision_time_evidence import capture_decision_time_evidence


def _evidence(**overrides):
    record = {
        "symbol": "WALT",
        "price": 1.25,
        "vwap_value": 1.20,
        "volume_pace_ratio": 2.1,
        "participation_gate": {"passed": True},
        "structure_gate": {"passed": True},
        "trigger_diagnostics": {
            "trigger": False,
            "checks": [{"condition": "entry trigger", "passed": False}],
        },
        "candidate_status": "EARLY",
        "qualified_for_watch": True,
        "qualified_for_entry": False,
        "qualified_for_alert": False,
    }
    record.update(overrides)
    return capture_decision_time_evidence(
        record, scan_id="scan-replay", scan_timestamp="2026-08-13T01:00:00+00:00"
    )


def test_replay_reconstructs_watch_state_without_market_data():
    result = replay_decision(_evidence())
    assert result["integrity_verified"] is True
    assert result["replay_state"] == "WATCH"
    assert result["recorded_status"] == "EARLY"
    assert "entry trigger" in result["blockers"]


def test_replay_reconstructs_entry_ready_state():
    result = replay_decision(_evidence(
        qualified_for_entry=True,
        trigger_diagnostics={"trigger": True, "checks": []},
    ))
    assert result["replay_state"] == "ENTRY_READY"
    assert result["trigger_result"] is True


def test_replay_refuses_mutated_history():
    evidence = _evidence()
    evidence["price"] = 99.0
    with pytest.raises(InvalidDecisionEvidence):
        replay_decision(evidence)

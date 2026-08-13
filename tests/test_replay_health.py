from mide.decision_time_evidence import capture_decision_time_evidence
from mide.replay_health import replay_health


def test_replay_health_classifies_legacy_healthy_and_fail():
    assert replay_health({"symbols": [{"symbol": "OLD"}]})["status"] == "LEGACY"
    evidence = capture_decision_time_evidence(
        {"symbol": "ABC"}, scan_id="s", scan_timestamp="2026-08-13T01:00:00+00:00"
    )
    assert replay_health({"symbols": [{"symbol": "ABC", "decision_time_evidence": evidence}]})["status"] == "HEALTHY"
    evidence["price"] = 99
    assert replay_health({"symbols": [{"symbol": "ABC", "decision_time_evidence": evidence}]})["status"] == "FAIL"

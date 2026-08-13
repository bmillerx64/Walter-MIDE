from mide.decision_time_evidence import capture_decision_time_evidence
from mide.replay_audit import audit_scan_replayability


def test_audit_distinguishes_valid_invalid_and_legacy_paths():
    valid = capture_decision_time_evidence(
        {"symbol": "AAA"}, scan_id="s1", scan_timestamp="2026-08-13T01:00:00+00:00"
    )
    invalid = capture_decision_time_evidence(
        {"symbol": "BBB"}, scan_id="s1", scan_timestamp="2026-08-13T01:00:00+00:00"
    )
    invalid["price"] = 9
    result = audit_scan_replayability({"scan_id": "s1", "symbols": [
        {"symbol": "AAA", "decision_time_evidence": valid},
        {"symbol": "BBB", "decision_time_evidence": invalid},
        {"symbol": "OLD"},
    ]})
    assert result["replayable"] == 1
    assert result["invalid_evidence"] == 1
    assert result["legacy_without_evidence"] == 1
    assert result["replayable_symbols"] == ["AAA"]
    assert result["invalid_symbols"] == ["BBB"]

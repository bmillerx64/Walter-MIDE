from mide.replay_manifest import replay_manifest


def test_manifest_contains_capture_replay_and_audit_layers():
    manifest = replay_manifest()
    assert "decision_time_evidence" in manifest
    assert "decision_replay" in manifest
    assert "flight_replay" in manifest
    assert "replay_audit" in manifest

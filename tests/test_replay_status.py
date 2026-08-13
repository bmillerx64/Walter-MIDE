from mide.replay_status import replay_status


def test_replay_status_is_read_only_and_not_yet_production_wired():
    status = replay_status()
    assert status["available"] is True
    assert status["mode"] == "read-only"
    assert status["integrity"] == "sha256"
    assert status["production_wiring"] is False

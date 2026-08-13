from mide.replay_version import REPLAY_SUBSYSTEM_VERSION


def test_replay_subsystem_has_explicit_version():
    assert REPLAY_SUBSYSTEM_VERSION == "1.0.0"

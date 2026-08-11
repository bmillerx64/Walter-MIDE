def test_version_import_activates_live_safety():
    import mide.version  # noqa: F401
    from mide import decision_engine
    assert decision_engine.behavioral_decision.__name__ == "_behavioral_decision_with_participation_floor"

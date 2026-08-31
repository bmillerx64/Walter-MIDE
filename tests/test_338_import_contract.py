def test_gs338_bootstrap_is_installed():
    import mide
    from mide import ui

    assert hasattr(mide, "__version__")
    assert getattr(ui.render_walter_mission_control, "_gs338_momentum_ignition_transition", False)
    assert getattr(ui.mission_control_recommendation, "_gs338_momentum_ignition_transition", False)

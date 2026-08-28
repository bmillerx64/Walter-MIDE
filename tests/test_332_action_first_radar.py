from mide import ui


def test_gs332_action_first_layout_is_installed():
    assert getattr(ui.mission_control_header_markup, "_gs332_action_first", False)
    assert getattr(ui.render_walter_mission_control, "_gs332_action_first", False)
    assert getattr(ui.render_escalation_engine, "_gs332_action_first", False)
    assert getattr(ui.render_early_setups, "_gs332_action_first", False)
    assert getattr(ui.data_integrity_markup, "_gs332_action_first", False)
    assert getattr(ui.market_session_quality_markup, "_gs332_action_first", False)


def test_gs332_keeps_supporting_renderers_available_below_action():
    assert callable(ui.render_escalation_engine._gs332_original)
    assert callable(ui.render_early_setups._gs332_original)
    assert callable(ui.render_walter_mission_control._gs332_original)


def test_gs332_quiets_top_verification_ribbons_without_deleting_logic():
    assert callable(ui.data_integrity_markup._gs332_original)
    assert callable(ui.market_session_quality_markup._gs332_original)

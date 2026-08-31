import mide
from mide import ui


def test_gs339_installed_on_mide_import():
    assert getattr(ui.render_walter_mission_control, "_gs339_preignition_vwap_reclaim", False)

    recommendation = getattr(ui, "mission_control_recommendation", None)
    if callable(recommendation):
        assert getattr(recommendation, "_gs339_preignition_vwap_reclaim", False)

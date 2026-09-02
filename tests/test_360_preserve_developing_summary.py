import inspect

from mide import gs349_operator_first_layout as layout
from mide import ui


def test_operator_first_render_contract_uses_multi_element_container():
    source = inspect.getsource(layout.install)
    assert "with ui.st.container():" in source
    assert getattr(
        ui.render_walter_mission_control,
        "_gs360_preserve_developing_summary",
        False,
    )

from __future__ import annotations

from pathlib import Path

from mide import gs407_sidebar_diagnostics_isolation as gs407
from mide.session_controls import (
    AUTO_SCAN_KEY,
    SCAN_REQUESTED_KEY,
    SCAN_RUNNING_KEY,
)


class FakeStreamlit:
    def __init__(self):
        self.session_state = {
            AUTO_SCAN_KEY: True,
            SCAN_RUNNING_KEY: False,
            SCAN_REQUESTED_KEY: False,
        }
        self.secrets = {}
        self.fragment_calls = 0
        self.toggle_calls = []
        self.text_calls = []
        self.button_calls = []
        self.success_messages = []
        self.error_messages = []
        self.caption_messages = []
        self.dataframes = []
        self.next_button_click = False

    def fragment(self, func):
        def wrapped(*args, **kwargs):
            self.fragment_calls += 1
            return func(*args, **kwargs)

        return wrapped

    def toggle(self, label, *args, **kwargs):
        self.toggle_calls.append((label, args, dict(kwargs)))
        key = kwargs.get("key")
        value = bool(kwargs.get("value", False))
        if key:
            self.session_state.setdefault(key, value)
            return bool(self.session_state[key])
        return value

    def text_input(self, label, *args, **kwargs):
        self.text_calls.append((label, args, dict(kwargs)))
        key = kwargs.get("key")
        value = str(kwargs.get("value", "") or "")
        if key:
            self.session_state.setdefault(key, value)
            return str(self.session_state[key])
        return value

    def button(self, label, *args, **kwargs):
        self.button_calls.append((label, args, dict(kwargs)))
        if kwargs.get("disabled"):
            return False
        clicked = self.next_button_click
        self.next_button_click = False
        return clicked

    def dataframe(self, rows, **kwargs):
        self.dataframes.append((rows, kwargs))

    def success(self, message):
        self.success_messages.append(message)

    def error(self, message):
        self.error_messages.append(message)

    def caption(self, message):
        self.caption_messages.append(message)


def test_connection_test_is_blocked_while_autoscan_or_scan_is_active():
    assert not gs407.connection_test_allowed({AUTO_SCAN_KEY: True, SCAN_RUNNING_KEY: False})
    assert not gs407.connection_test_allowed({AUTO_SCAN_KEY: False, SCAN_RUNNING_KEY: True})
    assert gs407.connection_test_allowed({AUTO_SCAN_KEY: False, SCAN_RUNNING_KEY: False})


def test_show_pass_toggle_runs_inside_fragment_without_requesting_scan():
    st = FakeStreamlit()
    gs407.install(st)

    result = st.toggle(gs407.SHOW_PASS_LABEL, value=False)

    assert result is False
    assert st.fragment_calls == 1
    assert st.toggle_calls[-1][2]["key"] == gs407.SHOW_PASS_KEY
    assert st.session_state[SCAN_REQUESTED_KEY] is False


def test_symbol_lookup_runs_inside_fragment_and_is_available_on_next_app_refresh():
    st = FakeStreamlit()
    st.session_state[gs407.SYMBOL_LOOKUP_KEY] = "ZTG"
    gs407.install(st)

    result = st.text_input(gs407.SYMBOL_LOOKUP_LABEL, placeholder="BIYA")

    assert result == "ZTG"
    assert st.fragment_calls == 1
    assert st.text_calls[-1][2]["key"] == gs407.SYMBOL_LOOKUP_KEY
    assert st.session_state[SCAN_REQUESTED_KEY] is False


def test_unrelated_widgets_remain_app_scoped():
    st = FakeStreamlit()
    gs407.install(st)

    st.toggle("Auto live scan every 60 seconds", value=True)
    st.text_input("Ticker to replay", value="FTFT")
    st.button("Run live scan")

    assert st.fragment_calls == 0


def test_connection_test_button_is_disabled_during_live_autoscan():
    st = FakeStreamlit()
    st.next_button_click = True
    gs407.install(st)

    outer_result = st.button(gs407.CONNECTION_TEST_LABEL, use_container_width=True)

    assert outer_result is False
    assert st.fragment_calls == 1
    assert st.button_calls[-1][2]["disabled"] is True
    assert any("Turn Auto live scan off" in item for item in st.caption_messages)
    assert st.session_state[SCAN_REQUESTED_KEY] is False


def test_manual_connection_test_executes_inside_fragment_not_legacy_app_if(monkeypatch):
    st = FakeStreamlit()
    st.session_state[AUTO_SCAN_KEY] = False
    st.next_button_click = True
    monkeypatch.setattr(
        gs407,
        "_run_webull_connection_test_rows",
        lambda _st: [{"Check": "credential loading", "Status": "PASS"}],
    )
    gs407.install(st)

    outer_result = st.button(gs407.CONNECTION_TEST_LABEL, use_container_width=True)

    assert outer_result is False
    assert st.session_state[gs407.CONNECTION_RESULT_KEY]["rows"][0]["Status"] == "PASS"
    assert st.success_messages[-1] == "Webull Connection Test: PASS"
    assert st.session_state[SCAN_REQUESTED_KEY] is False


def test_install_is_idempotent():
    st = FakeStreamlit()
    gs407.install(st)
    first_toggle = st.toggle
    first_text = st.text_input
    first_button = st.button

    gs407.install(st)

    assert st.toggle is first_toggle
    assert st.text_input is first_text
    assert st.button is first_button


def test_gs407_installs_after_gs406_in_final_chain():
    source = Path("mide/gs392_operator_order_audio.py").read_text()

    gs406_index = source.index("install_gs406()")
    gs407_index = source.index("install_gs407()")

    assert gs407_index > gs406_index
    assert (
        "from .gs407_sidebar_diagnostics_isolation import install as install_gs407"
        in source
    )


def test_scope_lock_does_not_touch_trading_authority():
    source = Path("mide/gs407_sidebar_diagnostics_isolation.py").read_text()

    assert "qualified_for_entry" not in source
    assert "vwap_distance_pct" not in source
    assert "supertrend" not in source.lower()
    assert "SCAN_REQUESTED_KEY" not in source

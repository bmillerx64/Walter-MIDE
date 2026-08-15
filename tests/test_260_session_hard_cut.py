from mide.session_controls import (
    DATA_MODE_KEY,
    PROVIDER_KEY,
    initialize_session_controls,
    provider_for_mode,
    select_data_mode,
)


def test_alpaca_mode_has_no_provider_mapping():
    assert provider_for_mode("Live Alpaca") is None
    assert provider_for_mode("Live Webull") == "WEBULL"


def test_initialize_repairs_persisted_alpaca_state_to_webull():
    state = {
        DATA_MODE_KEY: "Live Alpaca",
        PROVIDER_KEY: "ALPACA",
    }
    initialize_session_controls(state, default_mode="Live Webull", scan_running=False)
    assert state[DATA_MODE_KEY] == "Live Webull"
    assert state[PROVIDER_KEY] == "WEBULL"


def test_explicit_legacy_alpaca_selection_fails_closed_to_demo():
    state = {DATA_MODE_KEY: "Live Alpaca", PROVIDER_KEY: "ALPACA"}
    select_data_mode(state)
    assert state[DATA_MODE_KEY] == "Demo"
    assert state[PROVIDER_KEY] is None

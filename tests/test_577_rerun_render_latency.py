from pathlib import Path


def _source() -> str:
    return Path("app.py").read_text(encoding="utf-8")


def test_gs577_raw_scan_diagnostics_are_opt_in():
    source = _source()
    panel_start = source.index("with system_status_panel:")
    audio_boundary = source.index("\n_audio_scan_token = (", panel_start)
    panel = source[panel_start:audio_boundary]

    gate = panel.index('key="_walter_load_deep_system_status"')
    raw_json = panel.index("st.json(scan_diagnostics)")
    assert gate < raw_json
    assert 'value=False' in panel[gate - 160:gate + 80]


def test_gs577_heavy_system_status_sections_are_under_gate():
    source = _source()
    panel_start = source.index("with system_status_panel:")
    audio_boundary = source.index("\n_audio_scan_token = (", panel_start)
    panel = source[panel_start:audio_boundary]

    gate = panel.index("if load_deep_system_status:")
    for marker in (
        "operational_health = (",
        "post_universe = (",
        "verification = (",
        "strengthening = (",
    ):
        assert panel.index(marker) > gate


def test_gs588_process_observer_is_armed_before_heavy_render():
    source = _source()
    call = """arm_live_clock_engine(
    mode.startswith("Live ") and auto_refresh and live_possible,"""

    assert source.count(call) == 1
    call_index = source.index(call)
    assert call_index > source.index("clock = market_clock()")
    assert call_index < source.index("if records:", call_index)
    assert call_index < source.index('if active_tab == "Webull Debug":')
    assert "# GS588: process-owned cadence no longer depends on render completion." in source


def test_gs577_does_not_change_scan_or_trading_authority():
    source = _source()
    call_index = source.index("arm_live_clock_engine(\n    mode.startswith")
    tail = source[call_index:]
    assert "run_live(" not in tail
    assert "watchdog.run(" not in tail
    assert "submit_order(" not in tail
    assert "place_order(" not in tail

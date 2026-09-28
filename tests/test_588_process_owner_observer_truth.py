import importlib
from pathlib import Path

from mide import gs585_process_autoscan_service as service


def _app_source() -> str:
    return Path("app.py").read_text(encoding="utf-8")


def test_gs588_process_runtime_survives_module_reload():
    service._reset_for_tests()
    first = service._runtime()
    reloaded = importlib.reload(service)
    second = reloaded._runtime()

    assert second is first
    assert second["schema"] == 2


def test_gs588_runtime_is_anchored_to_process_watchdog():
    service._reset_for_tests()
    from mide.watchdog import PROCESS_SCAN_WATCHDOG

    runtime = service._runtime()
    assert getattr(
        PROCESS_SCAN_WATCHDOG,
        "_walter_gs585_process_autoscan_runtime",
    ) is runtime


def test_gs588_process_clock_uses_actual_process_start_truth():
    source = _app_source()
    start = source.index("def arm_live_clock_engine(")
    end = source.index("\ndef _run_live_pipeline(", start)
    clock = source[start:end]

    assert 'importlib.import_module(\n                "mide.gs585_process_autoscan_service"' in clock
    assert "process_snapshot.last_started_at" in clock
    assert "const processStartedAt = {process_started_ms};" in clock
    assert "const processRunning = {str(process_running).lower()};" in clock
    assert "processStartedAt + refreshMs" in clock


def test_gs588_observer_is_armed_before_heavy_dashboard_render():
    source = _app_source()
    completed = source.index('completed_scan = completed_scan_for_view(st.session_state, "Radar")')
    clock = source.index("arm_live_clock_engine(", completed)
    audit = source.index('if records:', clock)
    tail_note = source.index(
        "# GS588: process-owned cadence no longer depends on render completion."
    )

    assert completed < clock < audit < tail_note
    assert source.count(
        "process_autoscan_owned=True,"
    ) == 1


def test_gs588_does_not_touch_trading_authority():
    source = Path("mide/gs585_process_autoscan_service.py").read_text(
        encoding="utf-8"
    )
    forbidden = (
        "participation_score",
        "expansion_score",
        "qualified_for_entry",
        "qualified_for_alert",
        "mission_rank",
        "SuperTrend",
        "VWAP",
        "place_order(",
        "submit_order(",
    )
    assert not any(token in source for token in forbidden)

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
    assert second["schema"] == 3



def test_gs591_concurrent_first_runtime_creation_is_one_process_singleton():
    import builtins
    import threading

    runtime_key = service._RUNTIME_KEY
    lock_key = service._RUNTIME_INIT_LOCK_KEY
    sentinel = object()
    previous_runtime = builtins.__dict__.pop(runtime_key, sentinel)
    previous_lock = builtins.__dict__.pop(lock_key, sentinel)

    from mide.watchdog import PROCESS_SCAN_WATCHDOG

    previous_attr = getattr(
        PROCESS_SCAN_WATCHDOG,
        service._RUNTIME_ATTR,
        sentinel,
    )
    if previous_attr is not sentinel:
        delattr(PROCESS_SCAN_WATCHDOG, service._RUNTIME_ATTR)

    barrier = threading.Barrier(8)
    ids = []
    errors = []

    def worker():
        try:
            barrier.wait(timeout=5)
            ids.append(id(service._runtime()))
        except Exception as exc:
            errors.append(exc)

    threads = [threading.Thread(target=worker) for _ in range(8)]
    try:
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=10)

        assert not errors
        assert len(ids) == 8
        assert len(set(ids)) == 1
        assert getattr(PROCESS_SCAN_WATCHDOG, service._RUNTIME_ATTR) is service._runtime()
    finally:
        builtins.__dict__.pop(runtime_key, None)
        builtins.__dict__.pop(lock_key, None)
        if previous_runtime is not sentinel:
            builtins.__dict__[runtime_key] = previous_runtime
        if previous_lock is not sentinel:
            builtins.__dict__[lock_key] = previous_lock
        if previous_attr is sentinel:
            try:
                delattr(PROCESS_SCAN_WATCHDOG, service._RUNTIME_ATTR)
            except AttributeError:
                pass
        else:
            setattr(PROCESS_SCAN_WATCHDOG, service._RUNTIME_ATTR, previous_attr)


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

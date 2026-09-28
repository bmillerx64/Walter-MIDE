from datetime import datetime, timedelta, timezone
from pathlib import Path

from mide import gs585_process_autoscan_service as service


def _app_source() -> str:
    return Path("app.py").read_text(encoding="utf-8")


def test_gs585_process_service_anchors_start_to_start_deadline():
    service._reset_for_tests()
    started = datetime.now(timezone.utc)

    service.configure(
        enabled=False,
        refresh_seconds=60,
        worker=None,
    )
    service.note_scan_started(started)
    snap = service.snapshot()

    assert snap.last_started_at == started
    assert snap.next_due_monotonic is not None
    assert snap.last_error is None


def test_gs585_process_state_is_not_streamlit_session_state():
    service._reset_for_tests()
    state = service.process_state()
    state["sentinel"] = "process"
    assert service.process_state()["sentinel"] == "process"


def test_gs585_headless_pipeline_has_explicit_runtime_dependencies():
    source = _app_source()
    start = source.index("def _run_live_pipeline(")
    end = source.index("\ndef run_live(", start)
    pipeline = source[start:end]

    assert "runtime_state=None" in pipeline
    assert "runtime_secrets: dict | None = None" in pipeline
    assert "history_store=None" in pipeline
    assert "flight_recorder=None" in pipeline
    assert "ui_enabled: bool = True" in pipeline
    assert "runtime_state = st.session_state if runtime_state is None else runtime_state" in pipeline
    assert 'runtime_state["records"] = records' in pipeline
    assert "scan_context(runtime_state).pipeline = architecture" in pipeline


def test_gs585_process_worker_uses_watchdog_and_existing_completed_scan_publication():
    source = _app_source()
    start = source.index("def _run_process_autoscan(")
    end = source.index("\n\n# GS585: Streamlit/browser timers", start)
    worker = source[start:end]

    assert "PROCESS_SCAN_WATCHDOG" in worker
    assert "gs413._record_actual_scan_start(" in worker
    assert "service.note_scan_started(" in worker
    assert "service.note_scan_finished(" in worker
    assert "publish_scan_result(runtime_state, scan)" in worker
    assert "ui_enabled=False" in worker


def test_gs585_browser_no_longer_decides_automatic_due():
    source = _app_source()
    marker = "# GS585: automatic cadence is process-owned."
    start = source.index(marker)
    end = source.index("\n\nif mode.startswith", start)
    decision = source[start:end]

    assert "due = False" in decision
    assert "should_scan = bool(st.session_state[SCAN_REQUESTED_KEY])" in decision
    assert "completed_scan_for_view" not in decision
    assert "settings.refresh_seconds" not in decision


def test_gs585_browser_fragment_is_observer_not_process_scheduler():
    source = _app_source()
    start = source.index("def arm_live_clock_engine(")
    end = source.index("\ndef _run_live_pipeline(", start)
    scheduler = source[start:end]

    assert "process_autoscan_owned: bool = False" in scheduler
    assert "adopt_newer_process_scan()" in scheduler
    assert "if not process_autoscan_owned:" in scheduler
    assert "request_session_preserving_rerun()" in scheduler

    call = source[source.rindex("arm_live_clock_engine("):]
    assert "process_autoscan_owned=True" in call


def test_gs585_does_not_touch_trading_authority():
    source = Path("mide/gs585_process_autoscan_service.py").read_text(encoding="utf-8")
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

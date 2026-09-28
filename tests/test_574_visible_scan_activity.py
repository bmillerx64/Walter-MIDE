from pathlib import Path


def _app_source() -> str:
    return Path("app.py").read_text(encoding="utf-8")


def test_gs574_scan_status_is_not_hidden_in_system_status_expander():
    source = _app_source()
    run_live = source[source.index("def run_live("):source.index("\n\nshould_scan =", source.index("def run_live("))]

    assert 'with scan_activity_slot:' in run_live
    assert 'status = st.status("Walter is scanning…", expanded=True)' in run_live
    assert 'with scan_runtime_slot:' not in run_live


def test_gs574_scan_progress_uses_always_visible_slot():
    source = _app_source()
    pipeline = source[source.index("def _run_live_pipeline("):source.index("\ndef run_live(", source.index("def _run_live_pipeline("))]

    assert 'with scan_progress_slot:' in pipeline
    assert 'progress = st.progress(0, text="Starting Walter Architecture")' in pipeline
    assert 'scan_progress_slot.empty()' in pipeline


def test_gs574_visible_slots_are_created_before_collapsed_diagnostics():
    source = _app_source()

    activity = source.index("scan_activity_slot = st.empty()")
    progress = source.index("scan_progress_slot = st.empty()")
    system = source.index('system_status_panel = st.expander("System Status", expanded=False)')

    assert activity < system
    assert progress < system


def test_gs574_does_not_change_scan_scheduler_or_trading_logic():
    source = _app_source()
    scheduler = source[source.index("def arm_live_clock_engine("):source.index("\ndef _run_live_pipeline(", source.index("def arm_live_clock_engine("))]

    assert "@st.fragment(run_every=timedelta(seconds=interval))" in scheduler
    assert 'st.rerun(scope="app")' in scheduler
    assert "autoscan_request_due(" in scheduler

from pathlib import Path


def _scheduler_source() -> str:
    source = Path("app.py").read_text(encoding="utf-8")
    start = source.index("def arm_live_clock_engine(")
    end = source.index("\ndef _run_live_pipeline(", start)
    return source[start:end]


def test_gs575_auto_scan_tile_counts_down_without_server_reruns():
    scheduler = _scheduler_source()

    assert "const remainingMs = deadline - now;" in scheduler
    assert "setAutoScan(`Next ${{remainingSeconds}}s`" in scheduler
    assert "root.__walterLiveClockInterval = root.setInterval(tick, 1000);" in scheduler


def test_gs575_auto_scan_tile_shows_running_while_blocking_scan_is_due():
    scheduler = _scheduler_source()

    assert "setAutoScan(`● SCANNING ${{overdueSeconds}}s`" in scheduler
    assert "overdueSeconds <= 15" in scheduler
    assert "setAutoScan(`SCAN OVERDUE +${{overdueSeconds}}s`" in scheduler


def test_gs575_browser_indicator_does_not_own_scan_reruns():
    scheduler = _scheduler_source()

    assert "location.reload" in scheduler
    assert "Never use" in scheduler
    assert "@st.fragment(run_every=timedelta(seconds=interval))" in scheduler
    assert "autoscan_request_due(" in scheduler
    # The browser interval paints operator truth only; the Streamlit fragment
    # remains the sole owner of scheduled app reruns.
    js_start = scheduler.index('st.components.v1.html(')
    js = scheduler[js_start:]
    assert "location.reload(" not in js
    assert "st.rerun(" not in js


def test_gs575_disabled_state_is_explicit():
    scheduler = _scheduler_source()

    assert "setAutoScan('Disabled', '')" in scheduler

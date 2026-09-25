from pathlib import Path


def _scheduler_source() -> str:
    source = Path("app.py").read_text(encoding="utf-8")
    start = source.index("def arm_live_clock_engine(")
    end = source.index("\ndef _run_live_pipeline(", start)
    return source[start:end]


def test_gs565_deadline_heartbeat_is_bounded_to_five_seconds():
    scheduler = _scheduler_source()

    assert "interval = autoscan_wait_seconds(" in scheduler
    assert "scheduler_poll_seconds = min(max(1, int(interval)), 5)" in scheduler
    assert "@st.fragment(run_every=timedelta(seconds=scheduler_poll_seconds))" in scheduler


def test_gs565_heartbeat_never_requests_scan_before_existing_due_authority():
    scheduler = _scheduler_source()

    due = scheduler.index("if autoscan_request_due(")
    request = scheduler.index("st.session_state[SCAN_REQUESTED_KEY] = True")
    rerun = scheduler.index('st.rerun(scope="app")')

    assert due < request < rerun
    assert "_walter_live_scan_fragment_tick" not in scheduler
    assert "interval * 0.9" not in scheduler


def test_gs565_scheduler_change_is_orchestration_only():
    scheduler = _scheduler_source()

    forbidden = (
        "qualified_for_entry",
        "qualified_for_alert",
        "participation_score",
        "expansion_score",
        "vwap_distance_pct",
        ".bars(",
        ".snapshots(",
        "place_order(",
        "submit_order(",
        "location.reload(",
    )
    assert not any(token in scheduler for token in forbidden)

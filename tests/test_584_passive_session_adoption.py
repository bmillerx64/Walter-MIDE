from pathlib import Path


def _scheduler_source() -> str:
    source = Path("app.py").read_text(encoding="utf-8")
    start = source.index("def arm_live_clock_engine(")
    end = source.index("\ndef _run_live_pipeline(", start)
    return source[start:end]


def test_gs584_passive_observer_adopts_newer_process_scan_only():
    scheduler = _scheduler_source()

    assert "observer_poll_seconds = 5" in scheduler
    assert "@st.fragment(run_every=timedelta(seconds=observer_poll_seconds))" in scheduler
    assert "def adopt_newer_process_scan()" in scheduler
    observer = scheduler[
        scheduler.index("def adopt_newer_process_scan()"):
        scheduler.index("def request_session_preserving_rerun()")
    ]
    assert 'completed_scan_for_view(' in observer
    assert '"process observer"' in observer
    assert "observed_ms <= local_completed_ms" in observer
    assert 'st.rerun(scope="app")' in observer


def test_gs584_observer_never_requests_or_starts_scan():
    scheduler = _scheduler_source()
    observer = scheduler[
        scheduler.index("def adopt_newer_process_scan()"):
        scheduler.index("def request_session_preserving_rerun()")
    ]

    forbidden = (
        "st.session_state[SCAN_REQUESTED_KEY] = True",
        "autoscan_request_due(",
        "run_live(",
        "watchdog.run(",
        "request_scan(",
        "button.click(",
    )
    assert not any(token in observer for token in forbidden)


def test_gs584_browser_no_longer_manufactures_scan_requests():
    scheduler = _scheduler_source()

    assert "requestRunLiveScanWidget" not in scheduler
    assert "scheduler_starvation_recovery_ms" not in scheduler
    assert "RECOVERING AUTOSCAN" not in scheduler
    assert "AUTOSCAN RECOVERY WAITING" not in scheduler


def test_gs584_process_snapshot_precedes_session_exposure():
    source = Path("mide/completed_scan.py").read_text(encoding="utf-8")
    start = source.index("def store_completed_scan(")
    end = source.index("\ndef publish_scan_result(", start)
    store = source[start:end]

    process_publish = store.index("_publish_process_live_scan(scan)")
    session_context = store.index("context.completed_scan = scan")
    state_alias = store.index("state[COMPLETED_SCAN_KEY] = scan")
    assert process_publish < session_context < state_alias


def test_gs584_does_not_change_trading_authority():
    scheduler = _scheduler_source()
    forbidden = (
        "qualified_for_entry",
        "qualified_for_alert",
        "participation_score",
        "expansion_score",
        "place_order(",
        "submit_order(",
        "LiveWebullProvider(",
    )
    assert not any(token in scheduler for token in forbidden)

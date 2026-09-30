from pathlib import Path


def _scheduler_source() -> str:
    source = Path("app.py").read_text(encoding="utf-8")
    start = source.index("def arm_live_clock_engine(")
    end = source.index("\ndef _run_live_pipeline(", start)
    return source[start:end]


def test_gs581_bounded_heartbeat_preserves_gs567_no_perpetual_rerun_safety():
    scheduler = _scheduler_source()

    assert "scheduler_poll_seconds = min(max(1, int(interval)), 5)" in scheduler
    assert "@st.fragment(run_every=timedelta(seconds=scheduler_poll_seconds))" in scheduler
    assert 'request_latch_key = "_walter_live_scan_requested_for"' in scheduler


def test_gs581_full_app_rerun_is_due_guarded_and_per_baseline_latched():
    scheduler = _scheduler_source()
    request_start = scheduler.index("def request_session_preserving_rerun()")
    request_end = scheduler.index("\n\n        adopt_newer_process_scan()", request_start)
    request_fragment = scheduler[request_start:request_end]

    due = request_fragment.index("if not autoscan_request_due(")
    duplicate_guard = request_fragment.index(
        "if st.session_state.get(request_latch_key) == request_baseline:"
    )
    latch = request_fragment.index("st.session_state[request_latch_key] = request_baseline")
    request = request_fragment.index("st.session_state[SCAN_REQUESTED_KEY] = True")
    rerun = request_fragment.index('st.rerun(scope="app")')

    assert due < duplicate_guard < latch < request < rerun


def test_gs581_latch_clears_when_autoscan_is_disabled():
    scheduler = _scheduler_source()

    assert 'st.session_state.pop("_walter_live_scan_requested_for", None)' in scheduler


def test_gs581_scheduler_change_remains_orchestration_only():
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
        ".location.reload(",
    )
    assert not any(token in scheduler for token in forbidden)


def test_gs581_keeps_gs580_transport_proof_requirement():
    scheduler = _scheduler_source()

    recovery = scheduler[scheduler.index("const recoveryBaselinePresent = processOwned"):]
    assert "? processStartedAt > 0" in recovery
    assert ": attemptedAt > 0" in recovery
    assert "const recoveryDue = recoveryBaselinePresent" in recovery
    assert "&& nativeStreamlitConnecting()" in recovery
    assert "&& overdueSeconds * 1000 >= transportRecoveryMs" in recovery

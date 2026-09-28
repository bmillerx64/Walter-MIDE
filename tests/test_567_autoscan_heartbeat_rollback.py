from pathlib import Path


def _scheduler_source() -> str:
    source = Path("app.py").read_text(encoding="utf-8")
    start = source.index("def arm_live_clock_engine(")
    end = source.index("\ndef _run_live_pipeline(", start)
    return source[start:end]


def test_gs567_stability_invariant_survives_gs581_bounded_poll():
    scheduler = _scheduler_source()

    assert "scheduler_poll_seconds = min(max(1, int(interval)), 5)" in scheduler
    assert "@st.fragment(run_every=timedelta(seconds=scheduler_poll_seconds))" in scheduler
    assert 'request_latch_key = "_walter_live_scan_requested_for"' in scheduler


def test_gs581_full_app_rerun_is_due_guarded_and_latched():
    scheduler = _scheduler_source()

    due = scheduler.index("if not autoscan_request_due(")
    duplicate_guard = scheduler.index(
        "if st.session_state.get(request_latch_key) == request_baseline:"
    )
    latch = scheduler.index("st.session_state[request_latch_key] = request_baseline")
    request = scheduler.index("st.session_state[SCAN_REQUESTED_KEY] = True")
    rerun = scheduler.index('st.rerun(scope="app")')

    assert due < duplicate_guard < latch < request < rerun


def test_gs581_clears_request_latch_when_autoscan_is_disabled():
    scheduler = _scheduler_source()

    assert 'st.session_state.pop("_walter_live_scan_requested_for", None)' in scheduler


def test_gs581_scheduler_fix_is_orchestration_only():
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
    )
    assert not any(token in scheduler for token in forbidden)

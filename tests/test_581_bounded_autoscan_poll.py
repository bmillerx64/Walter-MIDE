from pathlib import Path


def _scheduler_source() -> str:
    source = Path("app.py").read_text(encoding="utf-8")
    start = source.index("def arm_live_clock_engine(")
    end = source.index("\ndef _run_live_pipeline(", start)
    return source[start:end]


def test_gs581_poll_fragment_is_bounded_to_five_seconds():
    scheduler = _scheduler_source()

    assert "scheduler_poll_seconds = min(max(1, int(interval)), 5)" in scheduler
    assert "@st.fragment(run_every=timedelta(seconds=scheduler_poll_seconds))" in scheduler


def test_gs581_non_due_poll_returns_before_full_app_rerun():
    scheduler = _scheduler_source()

    due_guard = scheduler.index("if not autoscan_request_due(")
    return_after_guard = scheduler.index("return", due_guard)
    full_rerun = scheduler.index('st.rerun(scope="app")')

    assert due_guard < return_after_guard < full_rerun


def test_gs581_one_full_app_request_per_scan_baseline():
    scheduler = _scheduler_source()

    assert 'request_latch_key = "_walter_live_scan_requested_for"' in scheduler
    assert "request_baseline = (" in scheduler
    assert "if st.session_state.get(request_latch_key) == request_baseline:" in scheduler
    assert "st.session_state[request_latch_key] = request_baseline" in scheduler


def test_gs581_does_not_touch_trading_or_provider_authority():
    scheduler = _scheduler_source()

    forbidden = (
        "qualified_for_entry",
        "qualified_for_alert",
        "participation_score",
        "expansion_score",
        "place_order(",
        "submit_order(",
        "claim_process_live_provider(",
        "LiveWebullProvider(",
    )
    assert not any(token in scheduler for token in forbidden)

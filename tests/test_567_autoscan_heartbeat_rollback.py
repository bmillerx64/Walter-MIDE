from pathlib import Path


def _scheduler_source() -> str:
    source = Path("app.py").read_text(encoding="utf-8")
    start = source.index("def arm_live_clock_engine(")
    end = source.index("\ndef _run_live_pipeline(", start)
    return source[start:end]


def test_gs567_restores_single_interval_fragment_not_five_second_heartbeat():
    scheduler = _scheduler_source()

    assert "@st.fragment(run_every=timedelta(seconds=interval))" in scheduler
    assert "scheduler_poll_seconds" not in scheduler
    assert "min(max(1, int(interval)), 5)" not in scheduler


def test_gs567_fragment_has_one_local_tick_guard_before_full_app_rerun():
    scheduler = _scheduler_source()

    assert 'tick_key = "_walter_live_scan_fragment_tick"' in scheduler
    assert "interval * 0.9" in scheduler
    assert "autoscan_request_due(" in scheduler
    assert scheduler.index("autoscan_request_due(") < scheduler.index(
        'st.rerun(scope="app")'
    )


def test_gs567_clears_fragment_tick_when_autoscan_is_disabled():
    scheduler = _scheduler_source()

    assert 'st.session_state.pop("_walter_live_scan_fragment_tick", None)' in scheduler


def test_gs567_scheduler_rollback_is_orchestration_only():
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

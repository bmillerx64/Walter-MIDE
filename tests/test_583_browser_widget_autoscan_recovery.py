from pathlib import Path


def _scheduler_source() -> str:
    source = Path("app.py").read_text(encoding="utf-8")
    start = source.index("def arm_live_clock_engine(")
    end = source.index("\ndef _run_live_pipeline(", start)
    return source[start:end]


def test_gs584_supersedes_browser_scheduler_recovery_without_touching_transport_recovery():
    scheduler = _scheduler_source()

    # GS580's CONNECTING-proven transport recovery remains.
    assert "nativeStreamlitConnecting()" in scheduler
    assert "RECONNECTING STREAMLIT" in scheduler

    # GS582/583 browser-side scheduler actions are retired: live evidence showed
    # they created/competed with a healthy process-wide cadence owner.
    assert "scheduler_starvation_recovery_ms" not in scheduler
    assert "walterSchedulerStarvationRecovery" not in scheduler
    assert "requestRunLiveScanWidget" not in scheduler
    assert "RECOVERING AUTOSCAN" not in scheduler
    assert "AUTOSCAN RECOVERY WAITING" not in scheduler


def test_gs584_preserves_existing_scan_authority():
    scheduler = _scheduler_source()

    assert "autoscan_request_due(" in scheduler
    assert "st.session_state[SCAN_REQUESTED_KEY] = True" in scheduler
    assert "@st.fragment(run_every=timedelta(seconds=scheduler_poll_seconds))" in scheduler
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

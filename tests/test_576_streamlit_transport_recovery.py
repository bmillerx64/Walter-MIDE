from pathlib import Path


def _scheduler_source() -> str:
    source = Path("app.py").read_text(encoding="utf-8")
    start = source.index("def arm_live_clock_engine(")
    end = source.index("\ndef _run_live_pipeline(", start)
    return source[start:end]


def test_gs576_transport_recovery_is_bounded_and_cooldown_latched():
    scheduler = _scheduler_source()

    assert "transport_recovery_ms = 45_000" in scheduler
    assert "transport_recovery_cooldown_ms = 90_000" in scheduler
    assert "const recoveryKey = 'walterTransportRecovery';" in scheduler
    assert "overdueSeconds * 1000 >= transportRecoveryMs" in scheduler
    assert ">= transportRecoveryCooldownMs" in scheduler


def test_gs576_transport_recovery_replaces_dead_browser_session_only():
    scheduler = _scheduler_source()

    recovery = scheduler[scheduler.index("// GS576 transport failover."):]
    assert "root.location.replace(root.location.href);" in recovery
    assert "RECONNECTING STREAMLIT" in recovery
    assert "st.rerun(" not in recovery
    assert "run_live(" not in recovery
    assert "scheduled_scan(" not in recovery
    assert "qualified_for_entry" not in recovery
    assert "place_order(" not in recovery
    assert "submit_order(" not in recovery


def test_gs576_recovery_latch_resets_on_new_scan_baseline_or_disable():
    scheduler = _scheduler_source()

    assert "recoveryState.baselineAt !== baselineAt" in scheduler
    assert "root.sessionStorage.removeItem(recoveryKey);" in scheduler
    assert "JSON.stringify({{baselineAt, recoveredAt: now}})" in scheduler


def test_gs576_normal_scheduler_remains_streamlit_fragment_owned():
    scheduler = _scheduler_source()

    assert "@st.fragment(run_every=timedelta(seconds=scheduler_poll_seconds))" in scheduler
    assert "autoscan_request_due(" in scheduler
    assert "st.session_state[SCAN_REQUESTED_KEY] = True" in scheduler
    assert 'st.rerun(scope="app")' in scheduler

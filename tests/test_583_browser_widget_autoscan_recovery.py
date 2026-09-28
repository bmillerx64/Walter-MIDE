from pathlib import Path


def _scheduler_source() -> str:
    source = Path("app.py").read_text(encoding="utf-8")
    start = source.index("def arm_live_clock_engine(")
    end = source.index("\ndef _run_live_pipeline(", start)
    return source[start:end]


def test_gs583_starvation_recovery_uses_native_streamlit_widget_event():
    scheduler = _scheduler_source()

    assert "const requestRunLiveScanWidget = () =>" in scheduler
    assert "root.document.querySelectorAll('button')" in scheduler
    assert "label === 'Run live scan'" in scheduler
    assert "button.click();" in scheduler

    recovery = scheduler[scheduler.index("const schedulerRecoveryDue = attemptedAt > 0"):]
    assert "const requested = requestRunLiveScanWidget();" in recovery
    assert "if (requested)" in recovery


def test_gs583_scheduler_recovery_does_not_try_top_level_navigation():
    scheduler = _scheduler_source()
    recovery = scheduler[scheduler.index("// GS583 scheduler-starvation fail-safe."):]
    recovery = recovery[:recovery.index("          }};\n          tick();")]

    assert "root.location.replace(root.location.href);" not in recovery
    assert "window.location" not in recovery


def test_gs583_only_latches_after_widget_request_succeeds():
    scheduler = _scheduler_source()
    recovery = scheduler[scheduler.index("// GS583 scheduler-starvation fail-safe."):]

    request = recovery.index("const requested = requestRunLiveScanWidget();")
    success = recovery.index("if (requested)")
    latch = recovery.index("root.sessionStorage.setItem(")
    waiting = recovery.index("AUTOSCAN RECOVERY WAITING")

    assert request < success < latch < waiting


def test_gs583_recovery_threshold_limits_live_staleness():
    scheduler = _scheduler_source()

    assert "scheduler_starvation_recovery_ms = 15_000" in scheduler
    assert "scheduler_starvation_recovery_cooldown_ms = 75_000" in scheduler


def test_gs583_preserves_existing_scan_authority():
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

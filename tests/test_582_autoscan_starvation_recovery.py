from pathlib import Path


def _scheduler_source() -> str:
    source = Path("app.py").read_text(encoding="utf-8")
    start = source.index("def arm_live_clock_engine(")
    end = source.index("\ndef _run_live_pipeline(", start)
    return source[start:end]


def test_gs582_has_separate_connected_scheduler_starvation_recovery():
    scheduler = _scheduler_source()

    assert "scheduler_starvation_recovery_ms = 15_000" in scheduler
    assert "scheduler_starvation_recovery_cooldown_ms = 75_000" in scheduler
    assert "const schedulerRecoveryKey = 'walterSchedulerStarvationRecovery';" in scheduler
    recovery = scheduler[scheduler.index("const schedulerRecoveryDue = attemptedAt > 0"):]
    assert "&& !nativeStreamlitConnecting()" in recovery
    assert "&& !visibleWalterScanActive()" in recovery
    assert ">= schedulerStarvationRecoveryMs" in recovery
    assert "RECOVERING AUTOSCAN" in recovery
    assert "requestRunLiveScanWidget()" in recovery


def test_gs582_gs583_recovery_never_requests_scan_while_visibly_active():
    scheduler = _scheduler_source()

    assert "const visibleWalterScanActive = () =>" in scheduler
    assert "text.includes('WALTER IS SCANNING')" in scheduler
    assert "text.includes('STARTING WALTER ARCHITECTURE')" in scheduler
    recovery = scheduler[scheduler.index("const schedulerRecoveryDue = attemptedAt > 0"):]
    active_guard = recovery.index("!visibleWalterScanActive()")
    request_pos = recovery.index("requestRunLiveScanWidget()")
    assert active_guard < request_pos


def test_gs582_recovery_is_per_baseline_and_cooldown_latched():
    scheduler = _scheduler_source()

    assert "schedulerRecoveryState.baselineAt !== baselineAt" in scheduler
    assert ">= schedulerStarvationRecoveryCooldownMs" in scheduler
    assert "JSON.stringify({{baselineAt, recoveredAt: now}})" in scheduler
    assert "root.sessionStorage.removeItem(schedulerRecoveryKey);" in scheduler


def test_gs582_preserves_trading_and_provider_authority():
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

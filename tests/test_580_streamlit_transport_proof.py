from pathlib import Path


def _scheduler_source() -> str:
    source = Path("app.py").read_text(encoding="utf-8")
    start = source.index("def arm_live_clock_engine(")
    end = source.index("\ndef _run_live_pipeline(", start)
    return source[start:end]


def test_gs580_transport_recovery_requires_native_streamlit_connecting():
    scheduler = _scheduler_source()

    assert "const nativeStreamlitConnecting = () =>" in scheduler
    assert "return /\\\\bCONNECTING\\\\b/.test(text);" in scheduler
    recovery = scheduler[scheduler.index("const recoveryDue = attemptedAt > 0"):]
    assert "&& nativeStreamlitConnecting()" in recovery
    assert "&& overdueSeconds * 1000 >= transportRecoveryMs" in recovery


def test_gs580_scan_lateness_alone_cannot_reload_healthy_session():
    scheduler = _scheduler_source()

    recovery = scheduler[scheduler.index("const recoveryDue = attemptedAt > 0"):]
    connecting_pos = recovery.index("nativeStreamlitConnecting()")
    overdue_pos = recovery.index("overdueSeconds * 1000 >= transportRecoveryMs")
    replace_pos = recovery.index("root.location.replace(root.location.href);")

    assert connecting_pos < overdue_pos < replace_pos
    assert "scan lateness is not transport failure" in scheduler

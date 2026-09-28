from pathlib import Path


def _scheduler_source() -> str:
    source = Path("app.py").read_text(encoding="utf-8")
    start = source.index("def arm_live_clock_engine(")
    end = source.index("\ndef _run_live_pipeline(", start)
    return source[start:end]


def test_gs579_successful_scan_anchors_browser_deadline_to_completed_scan():
    scheduler = _scheduler_source()

    assert "const deadline = attemptedAt > updatedAt" in scheduler
    assert "? attemptedAt + retryMs" in scheduler
    assert ": (updatedAt ? updatedAt + refreshMs : now);" in scheduler
    assert ": (attemptedAt ? attemptedAt + refreshMs : now);" not in scheduler


def test_gs579_reconnect_handoff_cannot_be_made_overdue_by_stale_attempt():
    scheduler = _scheduler_source()

    comment = scheduler[scheduler.index("// GS579: a reconnect"):]
    assert "process-wide completed" in comment
    assert "session-scoped last_scan_attempt" in comment
    assert "successful completed scan is" in comment

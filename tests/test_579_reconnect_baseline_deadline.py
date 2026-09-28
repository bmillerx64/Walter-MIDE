from pathlib import Path


def _scheduler_source() -> str:
    source = Path("app.py").read_text(encoding="utf-8")
    start = source.index("def arm_live_clock_engine(")
    end = source.index("\ndef _run_live_pipeline(", start)
    return source[start:end]


def test_gs588_process_start_anchors_browser_deadline_when_process_owned():
    scheduler = _scheduler_source()

    assert "const deadline = processOwned && processStartedAt > 0" in scheduler
    assert "? processStartedAt + refreshMs" in scheduler
    assert "attemptedAt > updatedAt" in scheduler
    assert "? attemptedAt + retryMs" in scheduler
    assert ": (updatedAt ? updatedAt + refreshMs : now)" in scheduler


def test_gs588_legacy_reconnect_fallback_remains_below_process_truth():
    scheduler = _scheduler_source()

    comment = scheduler[scheduler.index("// GS588: process start is"):]
    assert "production cadence truth" in comment
    assert "legacy fallback" in comment
    assert comment.index("processStartedAt + refreshMs") < comment.index(
        "attemptedAt > updatedAt"
    )

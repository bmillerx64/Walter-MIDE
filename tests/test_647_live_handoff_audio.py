from pathlib import Path


APP = Path("app.py")


def _source() -> str:
    return APP.read_text(encoding="utf-8")


def test_gs647_process_observer_polls_fast_without_scan_authority():
    source = _source()
    assert "observer_poll_seconds = 1" in source
    observer_start = source.index("def adopt_newer_process_scan()")
    observer_end = source.index("def request_session_preserving_rerun()", observer_start)
    observer = source[observer_start:observer_end]
    assert "completed_scan_for_view(" in observer
    assert "st.rerun(scope=\"app\")" in observer
    assert "SCAN_REQUESTED_KEY" not in observer
    assert "request_scan(" not in observer


def test_gs647_started_scan_does_not_invalidate_latest_completed_audio():
    source = _source()
    semantic_start = source.index("# GS647: semantic speech stays bound to completed evidence")
    semantic_end = source.index("# GS605:", semantic_start)
    semantic = source[semantic_start:semantic_end]
    assert "process_live_scan_snapshot()" in semantic
    assert "_audio_latest_process_scan.completed_at > completed_scan.completed_at" in semantic
    assert "last_started_at > completed_scan.completed_at" not in semantic


def test_gs647_process_audio_drops_only_superseded_completed_scan():
    source = _source()
    start = source.index("# GS647: register routine completed-scan browser audio")
    end = source.index("tab_names = [", start)
    block = source[start:end]
    assert "process_live_scan_snapshot()" in block
    assert "_process_audio_latest_completed.completed_at > completed_scan.completed_at" in block
    assert "dropped superseded process scan token" in block
    assert "newer_completed_scan={_newer_completed_scan_available}" in block
    assert "last_started_at > completed_scan.completed_at" not in block


def test_gs647_stale_passive_browser_recovers_before_multi_minute_lag():
    source = _source()
    live_clock_start = source.index("transport_recovery_ms = 45_000")
    live_clock_end = source.index("\ndef _run_live_pipeline(", live_clock_start)
    live_clock = source[live_clock_start:live_clock_end]
    assert "passive_observer_recovery_ms = 45_000" in live_clock
    assert "const passiveObserverRecoveryDue =" in live_clock
    assert "forceTopLevelRecovery()" in live_clock

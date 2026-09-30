from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_gs602_completed_scan_handoff_checks_freshness_before_deepcopy():
    source = (ROOT / "mide" / "completed_scan.py").read_text(encoding="utf-8")

    helper_start = source.index("def _newer_process_live_scan_snapshot(")
    helper_end = source.index("\n\ndef _state_wants_live_scan", helper_start)
    helper = source[helper_start:helper_end]

    assert "process_epoch = _completed_epoch(_PROCESS_LIVE_SCAN)" in helper
    assert "local_epoch >= process_epoch" in helper
    assert helper.index("local_epoch >= process_epoch") < helper.index(
        "return _safe_copy_scan(_PROCESS_LIVE_SCAN)"
    )


def test_gs602_semantic_audio_fails_closed_when_visible_scan_is_stale():
    source = (ROOT / "app.py").read_text(encoding="utf-8")

    start = source.index(
        "# GS602: semantic speech must be bound to the exact completed evidence"
    )
    end = source.index("\n# GS601: consume process-scan audio only after the entire dashboard render", start)
    block = source[start:end]

    assert "_audio_process_snapshot.last_started_at > completed_scan.completed_at" in block
    assert "if alerts and audio_triggered and alert_phrase:" in block
    assert "if not _audio_visible_scan_is_current:" in block
    assert "[WALTER AUDIO] semantic alert suppressed for stale visible scan" in block
    assert "escalation_alert_phrase(" not in block


def test_gs602_scope_preserves_scanner_and_trading_authority():
    completed_scan_source = (
        ROOT / "mide" / "completed_scan.py"
    ).read_text(encoding="utf-8")
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")

    helper_start = completed_scan_source.index(
        "def _newer_process_live_scan_snapshot("
    )
    helper_end = completed_scan_source.index(
        "\n\ndef _state_wants_live_scan", helper_start
    )
    helper = completed_scan_source[helper_start:helper_end]

    audio_start = app_source.index(
        "# GS602: semantic speech must be bound to the exact completed evidence"
    )
    audio_end = app_source.index("\n# GS601: consume process-scan audio only after the entire dashboard render", audio_start)
    audio = app_source[audio_start:audio_end]

    forbidden = (
        "qualified_for_entry =",
        "qualified_for_alert =",
        "participation_score =",
        "expansion_score =",
        "mission_rank =",
        "place_order(",
        "submit_order(",
        "PROCESS_SCAN_WATCHDOG.run",
        "note_scan_started(",
    )
    assert not any(token in helper for token in forbidden)
    assert not any(token in audio for token in forbidden)

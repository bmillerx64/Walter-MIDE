from datetime import datetime, timezone
from pathlib import Path

from mide import gs585_process_autoscan_service as service


ROOT = Path(__file__).resolve().parents[1]


def test_gs601_process_snapshot_exposes_current_inflight_stage():
    service._reset_for_tests()
    runtime = service._runtime()
    with runtime["lock"]:
        runtime["running"] = True

    started = datetime(2026, 9, 29, 18, 30, tzinfo=timezone.utc)
    service.note_scan_started(started)
    service.note_scan_stage("6/8 Participation · Scanner V2 enrichment", started)
    snapshot = service.snapshot()

    assert snapshot.running is True
    assert snapshot.current_stage == "6/8 Participation · Scanner V2 enrichment"
    assert snapshot.current_stage_started_at == started

    service.note_scan_finished(started)
    snapshot = service.snapshot()
    assert snapshot.current_stage == "Publishing completed scan"


def test_gs601_app_publishes_stage_and_subphase_diagnostics_without_new_authority():
    source = (ROOT / "app.py").read_text(encoding="utf-8")

    assert "def note_process_stage(detail: str) -> None:" in source
    assert "note_scan_stage(detail)" in source
    assert "6/8 Participation · Webull history and structure analysis" in source
    assert "6/8 Participation · velocity enrichment" in source
    assert "6/8 Participation · Scanner V2 enrichment" in source
    assert "6/8 Participation · decision materialization" in source
    assert "PARTICIPATION subphase timing %s" in source
    assert "POST-RANKING subphase timing %s" in source
    assert 'note_process_stage("Finalizing Flight Recorder evidence")' in source
    assert "post_stage_observer=note_process_stage" in source


def test_gs601_architecture_times_post_ranking_subphases_only():
    source = (ROOT / "mide" / "architecture.py").read_text(encoding="utf-8")

    assert "post_stage_observer: Callable[[str], None] | None = None" in source
    assert 'self.post_stage_timing["ledger_audit_completion_ms"]' in source
    assert 'self.post_stage_timing["decision_narratives_ms"]' in source
    assert 'self.post_stage_timing["candidate_history_persistence_ms"]' in source
    assert 'self.post_stage_timing["completed_result_publication_ms"]' in source
    assert 'self.post_stage_timing["runtime_validation_ms"]' in source
    assert 'self.post_stage_timing["architecture_verification_ms"]' in source

    start = source.index("        self.post_stage_timing = {}")
    end = source.index("\n        return results", start)
    diagnostic_block = source[start:end]
    forbidden = (
        "qualified_for_entry =",
        "qualified_for_alert =",
        "participation_score =",
        "expansion_score =",
        "place_order(",
        "submit_order(",
    )
    assert not any(token in diagnostic_block for token in forbidden)


def test_gs601_browser_scanning_label_includes_process_stage():
    source = (ROOT / "app.py").read_text(encoding="utf-8")

    assert 'getattr(process_snapshot, "current_stage", None)' in source
    assert 'f"● SCANNING {live_elapsed}s · {live_stage}"' in source
    assert "● SCANNING ${{elapsedSeconds}}s · ${{processStage}}" in source

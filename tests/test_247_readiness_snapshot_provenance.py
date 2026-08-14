from datetime import datetime, timezone

from mide.completed_scan import CompletedScan
from mide.live_evidence_observation import render_live_evidence_diagnostics


class _Column:
    def metric(self, *_args, **_kwargs):
        pass


class _Ui:
    def __init__(self):
        self.readiness = []
        self.info_messages = []

    def subheader(self, *_args):
        pass

    def caption(self, value):
        if str(value).startswith("Evidence readiness:"):
            self.readiness.append(value)

    def columns(self, count):
        return [_Column() for _ in range(count)]

    def success(self, *_args):
        pass

    def warning(self, *_args):
        pass

    def error(self, *_args):
        pass

    def info(self, value):
        self.info_messages.append(value)


def test_completed_scan_binds_same_readiness_snapshot_to_display_report():
    scan = CompletedScan(
        provider="WEBULL",
        records=[],
        diagnostics={},
        warnings=[],
        symbols_sampled=1,
        prefilter_count=0,
        completed_at=datetime.now(timezone.utc),
        source_label="test",
    )
    observation = scan.diagnostics["live_evidence_observation"]
    assert observation["readiness_snapshot"] is scan.diagnostics["evidence_readiness"]


def test_diagnostics_renders_stored_snapshot_not_recomputed_state():
    ui = _Ui()
    report = {
        "candidates_audited": 1,
        "trusted_count": 1,
        "caution_count": 0,
        "insufficient_count": 0,
        "trusted_pct": 100.0,
        "stale_evidence_count": 0,
        "incomplete_evidence_count": 0,
        "incoherent_evidence_count": 0,
        "nontrusted_elevated_count": 0,
        "nontrusted_elevated_symbols": [],
        "observations": [],
        "readiness_snapshot": {
            "status": "WATCH",
            "candidates_audited": 1,
            "trusted_pct": 95.0,
            "target_pct": 99.0,
            "target_met": False,
            "nontrusted_elevated_count": 0,
            "stale_evidence_count": 1,
            "incomplete_evidence_count": 0,
            "incoherent_evidence_count": 0,
            "reasons": ["stored snapshot marker"],
        },
    }
    render_live_evidence_diagnostics(ui, report)
    assert any("WATCH" in text and "95.0%" in text for text in ui.readiness)


def test_missing_snapshot_fails_visible_not_by_recomputation():
    ui = _Ui()
    report = {
        "candidates_audited": 0,
        "trusted_count": 0,
        "caution_count": 0,
        "insufficient_count": 0,
        "trusted_pct": None,
        "stale_evidence_count": 0,
        "incomplete_evidence_count": 0,
        "nontrusted_elevated_count": 0,
        "nontrusted_elevated_symbols": [],
        "observations": [],
    }
    render_live_evidence_diagnostics(ui, report)
    assert ui.info_messages == ["Evidence readiness snapshot unavailable for this completed scan."]

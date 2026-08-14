from mide.evidence_readiness_history import READINESS_HISTORY_KEY
from mide.live_evidence_observation import render_live_evidence_diagnostics


class Column:
    def __init__(self): self.metrics = []
    def metric(self, label, value): self.metrics.append((label, value))


class Ui:
    def __init__(self, history):
        self.session_state = {READINESS_HISTORY_KEY: history}
        self.subheaders, self.column_groups, self.messages, self.captions = [], [], [], []
    def subheader(self, value): self.subheaders.append(value)
    def caption(self, value): self.captions.append(value)
    def columns(self, count):
        group = [Column() for _ in range(count)]
        self.column_groups.append(group)
        return group
    def info(self, value): self.messages.append(("info", value))
    def success(self, value): self.messages.append(("success", value))
    def warning(self, value): self.messages.append(("warning", value))
    def error(self, value): self.messages.append(("error", value))


def readiness():
    return {"status": "READY", "trusted_pct": 100.0, "candidates_audited": 2,
            "nontrusted_elevated_count": 0, "stale_evidence_count": 0,
            "incomplete_evidence_count": 0, "incoherent_evidence_count": 0, "reasons": []}


def report(snapshot):
    return {"readiness_snapshot": snapshot, "candidates_audited": 2, "trusted_count": 2,
            "caution_count": 0, "insufficient_count": 0, "trusted_pct": 100.0,
            "stale_evidence_count": 0, "incomplete_evidence_count": 0,
            "incoherent_evidence_count": 0, "nontrusted_elevated_count": 0,
            "nontrusted_elevated_symbols": [], "observations": []}


def test_existing_diagnostics_call_renders_session_history_telemetry():
    snapshot = readiness()
    ui = Ui([
        {"completed_at": "2026-08-14T15:00:00+00:00", "readiness_snapshot": snapshot},
        {"completed_at": "2026-08-14T15:01:00+00:00", "readiness_snapshot": readiness()},
    ])
    render_live_evidence_diagnostics(ui, report(snapshot))
    assert "Live Evidence Reliability" in ui.subheaders
    assert "Session Evidence Reliability" in ui.subheaders
    metrics = ui.column_groups[-1]
    assert metrics[0].metrics == [("Measured Scans", 2)]
    assert metrics[1].metrics == [("Avg Reliability", "100.0%")]
    assert metrics[2].metrics == [("READY Rate", "100.0%")]


def test_ui_without_session_state_preserves_existing_render_contract():
    ui = Ui([])
    del ui.session_state
    render_live_evidence_diagnostics(ui, report(readiness()))
    assert "Live Evidence Reliability" in ui.subheaders
    assert "Session Evidence Reliability" not in ui.subheaders

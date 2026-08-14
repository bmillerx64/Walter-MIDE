from mide.evidence_readiness_diagnostics import render_evidence_readiness_diagnostics


class FakeColumn:
    def __init__(self):
        self.metrics = []

    def metric(self, label, value):
        self.metrics.append((label, value))


class FakeUi:
    def __init__(self):
        self.columns_created = [FakeColumn() for _ in range(4)]
        self.messages = []
        self.captions = []

    def subheader(self, value):
        self.subheader_value = value

    def caption(self, value):
        self.captions.append(value)

    def columns(self, count):
        assert count == 4
        return self.columns_created

    def success(self, value):
        self.messages.append(("success", value))

    def warning(self, value):
        self.messages.append(("warning", value))

    def error(self, value):
        self.messages.append(("error", value))

    def info(self, value):
        self.messages.append(("info", value))


def _report(status="READY", pct=100.0, audited=5):
    return {
        "status": status,
        "candidates_audited": audited,
        "trusted_pct": pct,
        "target_pct": 99.0,
        "target_met": status == "READY",
        "nontrusted_elevated_count": 0,
        "stale_evidence_count": 0,
        "incomplete_evidence_count": 0,
        "incoherent_evidence_count": 0,
        "reasons": ["snapshot reason"],
    }


def test_ready_snapshot_is_rendered_without_recomputation():
    ui = FakeUi()
    render_evidence_readiness_diagnostics(ui, _report())

    assert ui.subheader_value == "Evidence Readiness Gate"
    assert ui.columns_created[0].metrics == [("Readiness", "READY")]
    assert ui.columns_created[1].metrics == [("Evidence Reliability", "100.0%")]
    assert ui.columns_created[2].metrics == [("Reliability Target", "99.0%")]
    assert ui.columns_created[3].metrics == [("Candidates Audited", 5)]
    assert ui.messages[0][0] == "success"
    assert any("Diagnostics only" in caption for caption in ui.captions)


def test_unmeasured_snapshot_is_explicit_not_fabricated():
    ui = FakeUi()
    render_evidence_readiness_diagnostics(ui, _report("UNMEASURED", None, 0))

    assert ui.columns_created[1].metrics == [("Evidence Reliability", "N/A")]
    assert ui.messages[0][0] == "info"


def test_not_ready_snapshot_uses_error_operator_signal():
    ui = FakeUi()
    render_evidence_readiness_diagnostics(ui, _report("NOT READY", 82.5, 8))

    assert ui.columns_created[0].metrics == [("Readiness", "NOT READY")]
    assert ui.messages[0][0] == "error"

from mide.session_readiness_telemetry import (
    render_session_readiness_diagnostics,
    session_readiness_report,
)


def entry(status, pct, audited=5, **overrides):
    snapshot = {
        "status": status,
        "trusted_pct": pct,
        "candidates_audited": audited,
        "nontrusted_elevated_count": 0,
        "stale_evidence_count": 0,
        "incomplete_evidence_count": 0,
        "incoherent_evidence_count": 0,
    }
    snapshot.update(overrides)
    return {"readiness_snapshot": snapshot}


def test_empty_history_is_explicitly_unmeasured():
    report = session_readiness_report([])
    assert report["scans_recorded"] == 0
    assert report["measured_scans"] == 0
    assert report["average_reliability_pct"] is None
    assert report["ready_rate_pct"] is None
    assert report["session_target_met"] is False


def test_all_ready_history_sustains_99_percent_target():
    report = session_readiness_report([
        entry("READY", 100.0, 6),
        entry("READY", 99.0, 4),
    ])
    assert report["measured_scans"] == 2
    assert report["ready_scans"] == 2
    assert report["ready_rate_pct"] == 100.0
    assert report["average_reliability_pct"] == 99.5
    assert report["candidates_audited"] == 10
    assert report["session_target_met"] is True


def test_watch_or_not_ready_scan_prevents_sustained_target_claim():
    report = session_readiness_report([
        entry("READY", 100.0),
        entry("WATCH", 98.0, stale_evidence_count=1),
        entry("NOT READY", 80.0, nontrusted_elevated_count=1, incoherent_evidence_count=1),
    ])
    assert report["ready_scans"] == 1
    assert report["watch_scans"] == 1
    assert report["not_ready_scans"] == 1
    assert report["ready_rate_pct"] == 33.3
    assert report["average_reliability_pct"] == 92.7
    assert report["stale_evidence_count"] == 1
    assert report["nontrusted_elevated_count"] == 1
    assert report["incoherent_evidence_count"] == 1
    assert report["session_target_met"] is False


def test_unmeasured_history_does_not_fabricate_reliability_or_dilute_measured_rate():
    report = session_readiness_report([
        entry("UNMEASURED", None, 0),
        entry("READY", 100.0, 3),
    ])
    assert report["scans_recorded"] == 2
    assert report["measured_scans"] == 1
    assert report["unmeasured_scans"] == 1
    assert report["ready_rate_pct"] == 100.0
    assert report["average_reliability_pct"] == 100.0


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

    def columns(self, count):
        assert count == 4
        return self.columns_created

    def info(self, value):
        self.messages.append(("info", value))

    def success(self, value):
        self.messages.append(("success", value))

    def warning(self, value):
        self.messages.append(("warning", value))

    def caption(self, value):
        self.captions.append(value)


def test_renderer_surfaces_longitudinal_metrics_without_decision_behavior():
    ui = FakeUi()
    report = session_readiness_report([entry("READY", 100.0), entry("READY", 99.0)])
    render_session_readiness_diagnostics(ui, report)

    assert ui.subheader_value == "Session Evidence Reliability"
    assert ui.columns_created[0].metrics == [("Measured Scans", 2)]
    assert ui.columns_created[1].metrics == [("Avg Reliability", "99.5%")]
    assert ui.columns_created[2].metrics == [("READY Rate", "100.0%")]
    assert ui.columns_created[3].metrics == [("Target", "99.0%")]
    assert ui.messages[0][0] == "success"
    assert any("Diagnostics only" in caption for caption in ui.captions)

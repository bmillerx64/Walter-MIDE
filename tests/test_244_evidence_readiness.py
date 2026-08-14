from mide.evidence_readiness import (
    STATUS_NOT_READY,
    STATUS_READY,
    STATUS_UNMEASURED,
    STATUS_WATCH,
    evidence_readiness_report,
    evidence_readiness_summary,
)


def _report(**overrides):
    base = {
        "candidates_audited": 10,
        "trusted_pct": 100.0,
        "nontrusted_elevated_count": 0,
        "stale_evidence_count": 0,
        "incomplete_evidence_count": 0,
        "incoherent_evidence_count": 0,
    }
    base.update(overrides)
    return base


def test_ready_requires_99_percent_and_no_critical_mismatch():
    result = evidence_readiness_report(_report(trusted_pct=99.0))
    assert result["status"] == STATUS_READY
    assert result["target_met"] is True


def test_watch_is_near_target_without_critical_mismatch():
    result = evidence_readiness_report(_report(trusted_pct=95.0, stale_evidence_count=1))
    assert result["status"] == STATUS_WATCH
    assert result["target_met"] is False


def test_elevated_nontrusted_mismatch_is_not_ready():
    result = evidence_readiness_report(_report(trusted_pct=99.5, nontrusted_elevated_count=1))
    assert result["status"] == STATUS_NOT_READY
    assert result["target_met"] is False


def test_incoherent_evidence_is_not_ready():
    result = evidence_readiness_report(_report(trusted_pct=100.0, incoherent_evidence_count=1))
    assert result["status"] == STATUS_NOT_READY


def test_empty_scan_is_unmeasured_not_100_percent():
    result = evidence_readiness_report(_report(candidates_audited=0, trusted_pct=None))
    assert result["status"] == STATUS_UNMEASURED
    assert result["target_met"] is False


def test_summary_exposes_target_and_status():
    text = evidence_readiness_summary(_report(trusted_pct=99.0))
    assert "READY" in text
    assert "99.0%" in text
    assert "target 99%" in text

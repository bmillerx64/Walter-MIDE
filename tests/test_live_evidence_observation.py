from copy import deepcopy
from datetime import datetime, timezone

from mide.completed_scan import CompletedScan
from mide.live_evidence_observation import (
    live_evidence_observation,
    live_evidence_summary,
    render_live_evidence_diagnostics,
)


SCAN_TIME = datetime(2026, 8, 14, 12, 0, tzinfo=timezone.utc)


def candidate(symbol="WALT", **overrides):
    record = {
        "symbol": symbol,
        "price": 10.0,
        "volume": 100_000,
        "vwap_value": 9.8,
        "supertrend_bullish": True,
        "source_bar_timestamp": "2026-08-14T11:59:30+00:00",
        "timeframes": {"1m": {}},
        "candidate_status": "Watching",
        "conviction_score": 72,
    }
    record.update(overrides)
    return record


def observe(records):
    return live_evidence_observation(records, scan_timestamp=SCAN_TIME)


def test_all_trusted_candidates_aggregate_and_summary():
    report = observe([candidate("AAA"), candidate("BBB")])
    assert report["candidates_audited"] == 2
    assert report["trusted_count"] == 2
    assert report["caution_count"] == report["insufficient_count"] == 0
    assert report["trusted_pct"] == 100.0
    assert live_evidence_summary(report) == (
        "Evidence audit: 2 candidates · 2 TRUSTED · 0 CAUTION · "
        "0 INSUFFICIENT · 100% trusted · 0 elevated mismatches"
    )


def test_mixed_statuses_aggregate_and_expose_diagnostic_fields():
    report = observe([
        candidate("GOOD"),
        candidate("OLD", source_bar_timestamp="2026-08-14T11:50:00+00:00"),
        candidate("MISS", price=None, volume=None),
    ])
    assert (report["trusted_count"], report["caution_count"], report["insufficient_count"]) == (1, 1, 1)
    assert report["trusted_pct"] == 33.3
    observation = report["observations"][0]
    assert set(observation) == {
        "symbol", "evidence_status", "trusted", "completeness_pct", "fresh",
        "source_bar_age_seconds", "missing_fields", "coherence_failures",
        "elevated", "decision_state", "conviction",
    }
    assert observation["decision_state"] == "Watching"
    assert observation["conviction"] == 72


def test_stale_incomplete_and_incoherent_counts_are_independent():
    report = observe([
        candidate("STALE", source_bar_timestamp="2026-08-14T11:50:00+00:00"),
        candidate("INCOMPLETE", vwap_value=None),
        candidate("BAD", price=-1),
    ])
    assert report["stale_evidence_count"] == 1
    assert report["incomplete_evidence_count"] == 1
    assert report["incoherent_evidence_count"] == 1
    assert report["observations"][2]["coherence_failures"] == ["price_nonpositive"]


def test_zero_candidates_do_not_fabricate_reliability():
    report = observe([])
    assert report == {
        "candidates_audited": 0,
        "trusted_count": 0,
        "caution_count": 0,
        "insufficient_count": 0,
        "trusted_pct": None,
        "stale_evidence_count": 0,
        "incomplete_evidence_count": 0,
        "incoherent_evidence_count": 0,
        "nontrusted_elevated_count": 0,
        "nontrusted_elevated_symbols": [],
        "observations": [],
    }


def test_only_nontrusted_elevated_candidate_is_a_mismatch():
    report = observe([
        candidate("RISK", candidate_status="Strengthening", vwap_value=None),
        candidate("READY", candidate_status="Entry Ready"),
        candidate("ORDINARY", candidate_status="Watching", vwap_value=None),
    ])
    assert report["nontrusted_elevated_count"] == 1
    assert report["nontrusted_elevated_symbols"] == ["RISK"]
    assert report["observations"][0]["elevated"] is True
    assert report["observations"][1]["elevated"] is True
    assert report["observations"][1]["trusted"] is True
    assert report["observations"][2]["elevated"] is False


def test_observation_and_completed_scan_do_not_mutate_candidates_or_decisions():
    records = [candidate("SAFE", candidate_status="Entry Ready")]
    before = deepcopy(records)
    report = observe(records)
    scan = CompletedScan(
        provider="WEBULL", records=records, diagnostics={"decision": "unchanged"},
        warnings=[], symbols_sampled=1, prefilter_count=1,
        completed_at=SCAN_TIME, source_label="test",
    )
    assert records == before
    assert scan.records == before
    assert scan.diagnostics["decision"] == "unchanged"
    assert scan.diagnostics["live_evidence_observation"] == report


class FakeColumn:
    def __init__(self):
        self.metrics = []

    def metric(self, label, value):
        self.metrics.append((label, value))


class FakeUi:
    def __init__(self):
        self.column_groups = []
        self.warnings = []
        self.messages = []
        self.captions = []

    def subheader(self, _value):
        pass

    def caption(self, value):
        self.captions.append(value)

    def columns(self, count):
        group = [FakeColumn() for _ in range(count)]
        self.column_groups.append(group)
        return group

    def warning(self, value):
        self.warnings.append(value)
        self.messages.append(("warning", value))

    def success(self, value):
        self.messages.append(("success", value))

    def error(self, value):
        self.messages.append(("error", value))

    def info(self, value):
        self.messages.append(("info", value))


def test_diagnostics_rendering_handles_empty_observations():
    ui = FakeUi()
    render_live_evidence_diagnostics(ui, observe([]))
    assert len(ui.column_groups) == 2
    assert ui.column_groups[0][0].metrics == [("Readiness", "UNMEASURED")]
    assert ui.column_groups[1][0].metrics == [("Evidence Reliability %", "N/A")]
    assert ui.warnings == []

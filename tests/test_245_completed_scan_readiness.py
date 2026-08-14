from datetime import datetime, timezone

from mide.completed_scan import CompletedScan


def _trusted_record(symbol="WALT"):
    return {
        "symbol": symbol,
        "price": 1.25,
        "volume": 250000,
        "vwap_value": 1.20,
        "supertrend_bullish": True,
        "source_bar_timestamp": "2026-08-14T03:00:00+00:00",
        "timeframes": {"1m": {"ok": True}},
    }


def test_completed_scan_attaches_readiness_from_same_evidence_snapshot():
    scan = CompletedScan(
        provider="WEBULL",
        records=[_trusted_record()],
        diagnostics={"scan_completed": True},
        warnings=[],
        symbols_sampled=1,
        prefilter_count=1,
        completed_at=datetime(2026, 8, 14, 3, 0, 30, tzinfo=timezone.utc),
        source_label="Live WEBULL",
    )
    evidence = scan.diagnostics["live_evidence_observation"]
    readiness = scan.diagnostics["evidence_readiness"]
    assert evidence["trusted_pct"] == 100.0
    assert readiness["status"] == "READY"
    assert readiness["trusted_pct"] == evidence["trusted_pct"]
    assert readiness["target_pct"] == 99.0


def test_completed_scan_readiness_is_unmeasured_for_no_candidate_records():
    scan = CompletedScan(
        provider="WEBULL",
        records=[],
        diagnostics={"scan_completed": True},
        warnings=[],
        symbols_sampled=5,
        prefilter_count=0,
        completed_at=datetime(2026, 8, 14, 3, 0, 30, tzinfo=timezone.utc),
        source_label="Live WEBULL",
    )
    readiness = scan.diagnostics["evidence_readiness"]
    assert readiness["status"] == "UNMEASURED"
    assert readiness["trusted_pct"] is None
    assert readiness["target_met"] is False


def test_readiness_snapshot_does_not_mutate_candidate_record():
    record = _trusted_record()
    before = dict(record)
    CompletedScan(
        provider="WEBULL",
        records=[record],
        diagnostics={},
        warnings=[],
        symbols_sampled=1,
        prefilter_count=1,
        completed_at=datetime(2026, 8, 14, 3, 0, 30, tzinfo=timezone.utc),
        source_label="Live WEBULL",
    )
    assert record == before

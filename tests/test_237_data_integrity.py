from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone

from mide.data_integrity import (
    STATUS_AWAITING,
    STATUS_DEGRADED,
    STATUS_EMPTY,
    STATUS_FAILURE,
    STATUS_HEALTHY,
    record_integrity,
    records_integrity,
    scan_integrity_report,
)


NOW = datetime(2026, 8, 13, 12, 0, tzinfo=timezone.utc)


def good_record(symbol: str = "WALT") -> dict:
    return {
        "symbol": symbol,
        "price": 4.25,
        "volume": 125_000,
        "timestamp": NOW.isoformat(),
        "vwap_relation": "above",
        "participation_score": 82,
        "expansion_quality": "strong",
    }


def report(records, funnel=None, **kwargs):
    return scan_integrity_report(
        records,
        live=kwargs.pop("live", True),
        funnel_counts=funnel or {"universe": 100, "monitored": len(records)},
        now=NOW,
        **kwargs,
    )


def test_healthy_records_and_positive_universe_are_healthy():
    result = report([good_record()])
    assert result["status"] == STATUS_HEALTHY
    assert result["trust_score"] == 100


def test_zero_records_without_a_completed_scan_are_unmeasured_not_100_percent():
    result = scan_integrity_report([], live=True, scan_completed=False, now=NOW)
    assert result["status"] == STATUS_AWAITING
    assert result["trust_score"] is None
    assert result["record_integrity_pct"] is None
    assert result["freshness_pct"] is None
    assert result["record_count"] == 0
    assert result["unique_symbols"] == 0
    assert result["status_reason"] == "No completed scan has been measured yet."


def test_live_eighteen_of_eighteen_healthy_records_still_score_100_percent():
    records = [good_record(f"W{i:02d}") for i in range(18)]
    result = report(records, {"universe": 18, "monitored": 18})
    assert result["status"] == STATUS_HEALTHY
    assert result["record_count"] == 18
    assert result["unique_symbols"] == 18
    assert result["trust_score"] == 100


def test_zero_filtered_records_are_valid_empty_not_failure():
    result = report([], {"universe": 100, "stage_3_analysis": 0, "monitored": 0})
    assert result["status"] == STATUS_EMPTY
    assert result["empty_pass"] is True
    assert result["provider_failure"] is False
    assert result["trust_score"] == 100


def test_empty_pass_reason_identifies_first_zero_gate():
    result = report(
        [],
        {
            "universe": 32,
            "price": 13,
            "tradability": 13,
            "free_float": 0,
            "stage_3_analysis": 0,
            "monitored": 0,
        },
    )
    assert result["status"] == STATUS_EMPTY
    assert result["status_reason"] == "No symbols survived Free-Float Gate."


def test_live_explicitly_empty_universe_is_failure():
    result = report([], {"universe": 0})
    assert result["status"] == STATUS_FAILURE
    assert result["provider_failure"] is True


def test_requested_snapshots_with_none_received_is_failure():
    result = report([], {"universe": 100, "snapshots_requested": 12, "snapshots_received": 0})
    assert result["status"] == STATUS_FAILURE


def test_explicit_provider_error_is_failure():
    result = report([good_record()], provider_diagnostics={"error": "timeout"})
    assert result["status"] == STATUS_FAILURE


def test_one_invalid_record_degrades_integrity():
    malformed = good_record("BAD")
    malformed["price"] = float("nan")
    result = report([good_record(), malformed])
    assert result["record_integrity_pct"] == 50
    assert result["status"] == STATUS_DEGRADED


def test_stale_and_missing_timestamps_degrade_without_exception():
    stale = good_record("OLD")
    stale["timestamp"] = (NOW - timedelta(minutes=6)).isoformat()
    missing = good_record("NONE")
    del missing["timestamp"]
    stale_result = report([stale])
    missing_result = report([missing])
    assert stale_result["status"] == STATUS_DEGRADED
    assert stale_result["freshness_pct"] == 0
    assert missing_result["status"] == STATUS_DEGRADED
    assert missing_result["missing_timestamp_count"] == 1
    assert missing_result["freshness_pct"] is None


def test_duplicates_are_reported_and_lower_trust_without_changing_health_status():
    result = report([good_record(), good_record()])
    assert result["duplicate_symbols"] == ["WALT"]
    assert result["trust_score"] == 95
    assert result["status"] == STATUS_HEALTHY


def test_float_lookup_failure_degrades_but_actual_gate_failure_does_not():
    lookup = report([good_record()], {"universe": 10, "monitored": 1, "free_float_lookup_failures": 1})
    actual = report([good_record()], {"universe": 10, "monitored": 1, "free_float_actual_failures": 1})
    assert lookup["status"] == STATUS_DEGRADED
    assert lookup["provider_failure"] is False
    assert actual["status"] == STATUS_HEALTHY
    assert actual["provider_failure"] is False


def test_integrity_functions_never_mutate_inputs():
    records = [good_record(), good_record("TWO")]
    original = deepcopy(records)
    record_integrity(records[0], now=NOW)
    assert records == original
    records_integrity(records, now=NOW)
    assert records == original
    scan_integrity_report(records, live=True, funnel_counts={"universe": 10}, now=NOW)
    assert records == original

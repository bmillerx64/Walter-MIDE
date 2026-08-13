from copy import deepcopy
from datetime import datetime, timedelta, timezone

import pytest

from mide.calibration_records import (
    InvalidCalibrationRecord,
    aggregate_calibration_records,
    build_calibration_record,
    verify_calibration_record,
)
from mide.decision_time_evidence import capture_decision_time_evidence
from mide.forward_outcomes import measure_forward_outcome


START = datetime(2026, 8, 12, 14, 30, tzinfo=timezone.utc)


def evidence(symbol="WALT", scan_id="scan-232", price=10.0, conviction=82):
    return capture_decision_time_evidence(
        {
            "symbol": symbol,
            "price": price,
            "pct_change": 12.5,
            "volume": 500000,
            "dollar_volume": 5000000,
            "spread_pct": 0.8,
            "vwap_distance_pct": 2.2,
            "volume_pace_ratio": 3.4,
            "acceleration_ratio": 1.7,
            "supertrend_state": "bullish",
            "supertrend_bullish": True,
            "alignment_score": 4,
            "alignment_total": 5,
            "alignment_label": "strong",
            "quality_score": 79,
            "quality_grade": "A",
            "opportunity_score": 76,
            "conviction_score": conviction,
            "candidate_status": "Entry Window",
            "qualified_for_ranking": True,
            "qualified_for_watch": True,
            "qualified_for_entry": True,
            "qualified_for_alert": True,
            "trigger_diagnostics": {"trigger": "volume expansion"},
            "participation_gate": {"passed": True},
            "structure_gate": {"passed": True},
        },
        scan_id=scan_id,
        scan_timestamp=START,
        data_mode="test",
    )


def bars(*closes):
    output = []
    for minute, close in enumerate(closes, start=1):
        output.append(
            {
                "timestamp": START + timedelta(minutes=minute),
                "high": close + 0.5,
                "low": close - 0.5,
                "close": close,
            }
        )
    return output


def outcome_for(item, horizon, *closes):
    return measure_forward_outcome(item, bars(*closes), horizon_minutes=horizon)


def test_builds_integrity_verified_record_from_matching_lineage():
    item = evidence()
    outcome = outcome_for(item, 5, 10.2, 10.8, 11.0)
    record = build_calibration_record(item, outcome)

    assert verify_calibration_record(record)
    assert record["scan_id"] == "scan-232"
    assert record["symbol"] == "WALT"
    assert record["horizon_minutes"] == 5
    assert record["decision_features"]["conviction_score"] == 82
    assert record["outcome"]["mfe_pct"] == outcome["mfe_pct"]
    assert record["outcome"]["outcome_source"] == "strictly post-decision bars"


def test_calibration_record_owns_copies_and_cannot_mutate_sources():
    item = evidence()
    outcome = outcome_for(item, 5, 10.2, 10.8)
    evidence_before = deepcopy(item)
    outcome_before = deepcopy(outcome)

    record = build_calibration_record(item, outcome)
    record["decision_features"]["participation_gate"]["passed"] = False

    assert item == evidence_before
    assert outcome == outcome_before
    assert not verify_calibration_record(record)


def test_rejects_outcome_from_different_evidence_lineage():
    first = evidence(symbol="WALT", scan_id="scan-a")
    second = evidence(symbol="OTHER", scan_id="scan-b")
    mismatched = outcome_for(second, 5, 10.2, 10.8)

    with pytest.raises(InvalidCalibrationRecord, match="lineage mismatch"):
        build_calibration_record(first, mismatched)


def test_rejects_mutated_decision_evidence():
    item = evidence()
    outcome = outcome_for(item, 5, 10.2, 10.8)
    item["price"] = 99

    with pytest.raises(InvalidCalibrationRecord, match="evidence failed integrity"):
        build_calibration_record(item, outcome)


def test_aggregate_calibration_is_fixed_horizon_and_descriptive():
    first = evidence(scan_id="scan-one", conviction=82)
    second = evidence(scan_id="scan-two", conviction=65)
    third = evidence(scan_id="scan-three", conviction=50)

    records = [
        build_calibration_record(first, outcome_for(first, 5, 10.2, 10.8, 11.0)),
        build_calibration_record(second, outcome_for(second, 5, 9.8, 10.1, 10.3)),
        build_calibration_record(third, outcome_for(third, 10, 10.1, 9.7, 9.5)),
    ]

    summary = aggregate_calibration_records(records)

    assert summary["observations"] == 3
    assert summary["horizons"]["5"]["observations"] == 2
    assert summary["horizons"]["10"]["observations"] == 1
    assert summary["horizons"]["5"]["positive_end_return_rate_pct"] == 100
    assert summary["policy_authority"].startswith("none")


def test_aggregate_rejects_mutated_record_instead_of_silently_using_it():
    item = evidence()
    record = build_calibration_record(item, outcome_for(item, 5, 10.2, 10.8))
    record["outcome"]["end_return_pct"] = 999

    with pytest.raises(InvalidCalibrationRecord, match="integrity verification"):
        aggregate_calibration_records([record])

from copy import deepcopy

import pytest

from mide.calibration_records import build_calibration_record, InvalidCalibrationRecord
from mide.calibration_slices import slice_calibration_records
from mide.decision_time_evidence import capture_decision_time_evidence


def _record(symbol, *, quality, grade, entry_ready, end_return, mfe, mae, horizon=15):
    evidence = capture_decision_time_evidence(
        {
            "symbol": symbol,
            "price": 1.0,
            "quality_score": quality,
            "quality_grade": grade,
            "conviction_v2_score": quality,
            "candidate_status": "ENTRY READY" if entry_ready else "WATCH",
            "qualified_for_entry": entry_ready,
            "vwap_distance_pct": 2.0,
            "volume_pace_ratio": 5.0,
        },
        scan_id=f"scan-{symbol}",
        scan_timestamp="2026-08-13T14:30:00+00:00",
        data_mode="LIVE",
    )
    outcome = {
        "scan_id": evidence["scan_id"],
        "symbol": evidence["symbol"],
        "decision_timestamp": evidence["scan_timestamp"],
        "evidence_sha256": evidence["evidence_sha256"],
        "horizon_minutes": horizon,
        "mfe_pct": mfe,
        "mae_pct": mae,
        "end_return_pct": end_return,
        "time_to_mfe_seconds": 120.0,
        "bars_observed": horizon,
        "entry_price": 1.0,
        "max_forward_high": 1 + mfe / 100,
        "min_forward_low": 1 + mae / 100,
        "outcome_source": "strictly post-decision bars",
    }
    return build_calibration_record(evidence, outcome)


def test_slices_compare_decision_time_groups_without_policy_authority():
    records = [
        _record("AAA", quality=82, grade="A", entry_ready=True, end_return=8, mfe=14, mae=-3),
        _record("BBB", quality=84, grade="A", entry_ready=True, end_return=4, mfe=10, mae=-2),
        _record("CCC", quality=55, grade="C", entry_ready=False, end_return=-5, mfe=3, mae=-9),
    ]
    result = slice_calibration_records(records, dimension="quality_grade")
    slices = result["horizons"]["15"]["slices"]
    assert slices["A"]["observations"] == 2
    assert slices["A"]["average_end_return_pct"] == 6
    assert slices["A"]["positive_end_return_rate_pct"] == 100
    assert slices["C"]["average_end_return_pct"] == -5
    assert result["policy_authority"].startswith("none")


def test_slices_never_mix_forward_horizons():
    records = [
        _record("AAA", quality=80, grade="A", entry_ready=True, end_return=5, mfe=9, mae=-2, horizon=5),
        _record("BBB", quality=80, grade="A", entry_ready=True, end_return=12, mfe=18, mae=-4, horizon=30),
    ]
    result = slice_calibration_records(records, dimension="qualified_for_entry")
    assert result["horizons"]["5"]["slices"]["True"]["average_end_return_pct"] == 5
    assert result["horizons"]["30"]["slices"]["True"]["average_end_return_pct"] == 12


def test_minimum_sample_gate_hides_undersized_slices():
    records = [_record("AAA", quality=80, grade="A", entry_ready=True, end_return=5, mfe=9, mae=-2)]
    result = slice_calibration_records(records, dimension="quality_grade", min_observations=2)
    assert result["horizons"]["15"]["slices"] == {}


def test_mutated_record_is_rejected():
    record = _record("AAA", quality=80, grade="A", entry_ready=True, end_return=5, mfe=9, mae=-2)
    mutated = deepcopy(record)
    mutated["decision_features"]["quality_grade"] = "F"
    with pytest.raises(InvalidCalibrationRecord, match="integrity"):
        slice_calibration_records([mutated], dimension="quality_grade")


def test_unsupported_dimension_fails_closed():
    record = _record("AAA", quality=80, grade="A", entry_ready=True, end_return=5, mfe=9, mae=-2)
    with pytest.raises(ValueError, match="unsupported"):
        slice_calibration_records([record], dimension="future_magic")

from datetime import datetime, timedelta, timezone

import pytest

from mide.decision_time_evidence import capture_decision_time_evidence
from mide.forward_outcomes import InvalidOutcomeWindow, measure_forward_outcome


def _evidence():
    return capture_decision_time_evidence(
        {"symbol": "ABC", "price": 1.00, "qualified_for_watch": True},
        scan_id="scan-231",
        scan_timestamp=datetime(2026, 8, 13, 14, 0, tzinfo=timezone.utc),
        data_mode="Live Webull",
    )


def test_forward_outcome_measures_mfe_mae_without_mutating_evidence():
    evidence = _evidence()
    original = dict(evidence)
    t0 = datetime(2026, 8, 13, 14, 0, tzinfo=timezone.utc)
    bars = [
        {"timestamp": t0, "high": 9.00, "low": 0.10, "close": 8.00},  # decision bar excluded
        {"timestamp": t0 + timedelta(minutes=1), "high": 1.05, "low": 0.98, "close": 1.02},
        {"timestamp": t0 + timedelta(minutes=3), "high": 1.20, "low": 1.00, "close": 1.15},
        {"timestamp": t0 + timedelta(minutes=6), "high": 2.00, "low": 0.50, "close": 1.50},  # beyond horizon
    ]

    outcome = measure_forward_outcome(evidence, bars, horizon_minutes=5)

    assert outcome["bars_observed"] == 2
    assert outcome["mfe_pct"] == pytest.approx(20.0)
    assert outcome["mae_pct"] == pytest.approx(-2.0)
    assert outcome["end_return_pct"] == pytest.approx(15.0)
    assert outcome["time_to_mfe_seconds"] == 180
    assert outcome["outcome_source"] == "strictly post-decision bars"
    assert evidence == original


def test_forward_outcome_fails_closed_without_post_decision_bars():
    evidence = _evidence()
    t0 = datetime(2026, 8, 13, 14, 0, tzinfo=timezone.utc)
    with pytest.raises(InvalidOutcomeWindow, match="strictly forward"):
        measure_forward_outcome(
            evidence,
            [{"timestamp": t0, "high": 1.2, "low": 0.8, "close": 1.1}],
            horizon_minutes=5,
        )


def test_forward_outcome_rejects_tampered_decision_evidence():
    evidence = _evidence()
    evidence["price"] = 0.50
    with pytest.raises(InvalidOutcomeWindow, match="integrity"):
        measure_forward_outcome(evidence, [], horizon_minutes=5)

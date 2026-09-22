from mide.scanner_v2 import trigger_diagnostics


def _base():
    return {
        "symbol": "SBFM",
        "supertrend_bullish": True,
        "supertrend_flip": False,
        "supertrend_flipped_last_10m": False,
        "vwap_distance_pct": 1.12,
        "strengthening_vwap_gate": {"distance_pct": 1.12},
        "expansion_quality": 71.0,
        "trend_confirmation_sequence": {
            "progression_count": 4,
            "conflict_count": 0,
        },
        "participation_surge_diagnostics": {
            "participation_score": 79.0,
            "expansion_quality": 71.0,
            "volume_acceleration": {"3m": 3.89},
            "dollar_flow_acceleration": {"3m": 3.94},
        },
    }


def test_sbfm_like_continuation_can_satisfy_st_lock_without_fresh_flip():
    result = trigger_diagnostics(_base())
    checks = {row["condition"]: row for row in result["checks"]}

    assert checks["supertrend_flip"]["passed"] is True
    assert "continuation re-ignition" in checks["supertrend_flip"]["passed_reason"]
    assert result["continuation_reignition"]["active"] is True
    assert result["passed"] is True


def test_continuation_reignition_does_not_override_weak_participation():
    record = _base()
    record["participation_surge_diagnostics"]["participation_score"] = 61.0

    result = trigger_diagnostics(record)
    checks = {row["condition"]: row for row in result["checks"]}

    assert checks["supertrend_flip"]["passed"] is False
    assert result["continuation_reignition"]["active"] is False


def test_continuation_reignition_does_not_override_extension():
    record = _base()
    record["vwap_distance_pct"] = 1.8
    record["strengthening_vwap_gate"]["distance_pct"] = 1.8

    result = trigger_diagnostics(record)
    checks = {row["condition"]: row for row in result["checks"]}

    assert checks["supertrend_flip"]["passed"] is False
    assert result["continuation_reignition"]["active"] is False


def test_continuation_reignition_requires_multitimeframe_confirmation():
    record = _base()
    record["trend_confirmation_sequence"]["progression_count"] = 2

    result = trigger_diagnostics(record)
    checks = {row["condition"]: row for row in result["checks"]}

    assert checks["supertrend_flip"]["passed"] is False
    assert result["continuation_reignition"]["active"] is False


def test_continuation_reignition_requires_fresh_three_minute_reacceleration():
    record = _base()
    record["participation_surge_diagnostics"]["volume_acceleration"]["3m"] = 1.2
    record["participation_surge_diagnostics"]["dollar_flow_acceleration"]["3m"] = 1.3

    result = trigger_diagnostics(record)
    checks = {row["condition"]: row for row in result["checks"]}

    assert checks["supertrend_flip"]["passed"] is False
    assert result["continuation_reignition"]["active"] is False


def test_fresh_flip_path_remains_intact():
    record = _base()
    record["supertrend_flip"] = True
    record["trend_confirmation_sequence"]["progression_count"] = 1
    record["participation_surge_diagnostics"]["participation_score"] = 60.0
    record["expansion_quality"] = 55.0
    record["participation_surge_diagnostics"]["expansion_quality"] = 55.0
    record["participation_surge_diagnostics"]["volume_acceleration"]["3m"] = 1.0
    record["participation_surge_diagnostics"]["dollar_flow_acceleration"]["3m"] = 1.0

    result = trigger_diagnostics(record)

    assert result["checks"][1]["passed"] is True
    assert result["continuation_reignition"]["active"] is False

from mide.scanner_v2 import trigger_diagnostics


def _record(**overrides):
    record = {
        "symbol": "ONCO",
        "supertrend_bullish": True,
        "supertrend_flip": False,
        "supertrend_flipped_last_10m": True,
        "supertrend_flip_age_seconds": 113.2,
        "maturation_freshness_authority": "SOURCE_AGE_ADJUSTED_MATURATION_FRESHNESS",
        "vwap_distance_pct": 1.509,
        "strengthening_vwap_gate": {"distance_pct": 1.509},
        "expansion_quality": 59.8,
        "participation_surge_diagnostics": {
            "participation_score": 94.6,
            "expansion_quality": 59.8,
            "volume_acceleration": {"3m": 1.0},
            "dollar_flow_acceleration": {"3m": 1.0},
        },
        "trend_confirmation_sequence": {
            "progression_count": 0,
            "conflict_count": 0,
        },
    }
    record.update(overrides)
    return record


def _check(result, condition):
    return next(
        check for check in result["checks"]
        if check["condition"] == condition
    )


def test_gs561_source_aged_1m_flip_satisfies_existing_st_lock():
    result = trigger_diagnostics(_record())

    assert result["passed"] is True
    assert _check(result, "supertrend_flip")["passed"] is True
    assert result["failed_conditions"] == []


def test_gs561_legacy_last_10m_boolean_does_not_gain_entry_authority():
    result = trigger_diagnostics(
        _record(maturation_freshness_authority=None)
    )

    assert result["passed"] is False
    assert _check(result, "supertrend_flip")["passed"] is False
    assert result["failed_conditions"] == ["supertrend_flip"]


def test_gs561_source_aged_1m_flip_still_obeys_ten_minute_expiry():
    result = trigger_diagnostics(
        _record(supertrend_flip_age_seconds=601.0)
    )

    assert result["passed"] is False
    assert _check(result, "supertrend_flip")["passed"] is False
    assert result["failed_conditions"] == ["supertrend_flip"]

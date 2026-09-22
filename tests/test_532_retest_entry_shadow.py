from mide.gs532_retest_entry_shadow import retest_entry_shadow


def _record(**overrides):
    base = {
        "vwap_distance_pct": 0.5,
        "participation_surge_diagnostics": {"participation_score": 67},
        "expansion_quality": 63,
        "vwap_relation": "above",
        "timeframes": {
            "30s": {"available": True, "bullish": True, "above_vwap": True},
            "1m": {"available": True, "bullish": True, "above_vwap": True},
        },
        "multitimeframe_maturation": {
            "three_minute_st_retest_event": {
                "available": True,
                "active_memory": True,
            }
        },
    }
    base.update(overrides)
    return base


def test_retest_shadow_can_reach_ready_without_recent_flip():
    result = retest_entry_shadow(_record())
    assert result["shadow_entry_ready"] is True
    assert result["failed_conditions"] == []
    assert result["trading_authority_changed"] is False


def test_retest_shadow_keeps_vwap_antichase():
    result = retest_entry_shadow(_record(vwap_distance_pct=6.0))
    assert result["shadow_entry_ready"] is False
    assert "vwap_entry_window" in result["failed_conditions"]


def test_retest_shadow_requires_held_retest():
    record = _record()
    record["multitimeframe_maturation"]["three_minute_st_retest_event"]["active_memory"] = False
    result = retest_entry_shadow(record)
    assert result["shadow_entry_ready"] is False
    assert "three_minute_retest_held" in result["failed_conditions"]


def test_retest_shadow_requires_lower_tf_repair():
    record = _record()
    record["timeframes"]["1m"]["above_vwap"] = False
    result = retest_entry_shadow(record)
    assert result["shadow_entry_ready"] is False
    assert "lower_timeframe_repair_complete" in result["failed_conditions"]

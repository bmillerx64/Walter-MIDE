from mide.gs305_second_wave_attention import attention_evaluation
from mide.early_setup import top_timing_setups


def _record(**updates):
    record = {
        "symbol": "MMA",
        "price": 0.82,
        "pct_change": 115.0,
        "dollar_volume": 20_000_000,
        "vwap_relation": "above",
        "vwap_distance_pct": 3.0,
        "supertrend_bullish": True,
        "volume_acceleration": 2.0,
        "rvol_proxy": 6.0,
        "volume_above_preceding_15m_pace": True,
        "price_change_10m_pct": 8.0,
        "broke_previous_15m_high_with_volume": True,
        "opportunity_pulse_previous": {"pct_change": 55.0},
        "early_setup": {"base_qualified": False, "timing_state": "Discovered"},
        "structure": {"score": 55.0, "state": "BUILDING"},
    }
    record.update(updates)
    return record


def test_mma_style_second_wave_gets_look_now_attention():
    result = attention_evaluation(_record(vwap_distance_pct=2.0))
    assert result["eligible"] is True
    assert result["second_wave"] is True
    assert result["label"] == "LOOK NOW · RE-IGNITION"


def test_extended_second_wave_is_still_shown_but_called_chase():
    result = attention_evaluation(_record(vwap_distance_pct=12.0))
    assert result["eligible"] is True
    assert result["label"] == "CHASE / WAIT FOR RESET"


def test_halt_or_suspension_is_attention_not_trade_qualification():
    result = attention_evaluation(
        _record(
            pct_change=42.0,
            halted=True,
            vwap_relation="below",
            supertrend_bullish=False,
            volume_acceleration=0.0,
            rvol_proxy=0.0,
            broke_previous_15m_high_with_volume=False,
        )
    )
    assert result["eligible"] is True
    assert result["halted"] is True
    assert result["label"] == "HALTED / WATCH RESUME"


def test_ordinary_low_activity_name_is_not_promoted_for_attention():
    result = attention_evaluation(
        _record(
            pct_change=4.0,
            dollar_volume=100_000,
            volume_acceleration=0.5,
            rvol_proxy=1.0,
            volume_above_preceding_15m_pace=False,
            price_change_10m_pct=0.5,
            broke_previous_15m_high_with_volume=False,
            opportunity_pulse_previous={},
        )
    )
    assert result["eligible"] is False


def test_structure_engine_selection_can_include_attention_only_major_mover():
    record = _record(vwap_distance_pct=2.0)
    selected = top_timing_setups([record], limit=5)
    assert [item["symbol"] for item in selected] == ["MMA"]
    assert selected[0]["walter_attention"]["second_wave"] is True
    assert selected[0]["structure"]["state"] == "LOOK NOW · RE-IGNITION"
    # Selection is display-only and must not mutate the source record.
    assert "walter_attention" not in record
    assert record["structure"]["state"] == "BUILDING"

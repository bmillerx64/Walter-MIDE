from mide.ui import radar_table


def sample_record(**overrides):
    record = {
        "symbol": "AAA",
        "price": 1.23,
        "pct_change": 4.5,
        "volume": 1_000_000,
        "dollar_volume": 1_230_000,
        "attention_score": 77.0,
        "market_dominance_score": 12.0,
        "participation_score": 66.0,
        "participation_tier": "High",
        "opportunity_score": 72.0,
        "conviction_score": 70.0,
        "velocity": 0,
        "status": "WATCH NOW",
        "vwap_relation": "above",
        "supertrend_bullish": True,
        "rvol_proxy": 3.1,
        "volume_acceleration": 1.4,
        "spread_pct": 0.8,
    }
    record.update(overrides)
    return record


def test_radar_table_does_not_display_velocity_placeholder_column():
    table = radar_table([sample_record()])

    assert "Velocity" not in table.columns
    assert 0 not in table.iloc[0].tolist()


def test_radar_table_alignment_preserves_other_metric_columns():
    table = radar_table([sample_record()])

    assert list(table.columns) == [
        "Symbol",
        "Price",
        "% Chg",
        "Feed Vol",
        "$ Vol",
        "Attention",
        "Dominance",
        "Participation",
        "Tier",
        "Opp.",
        "Conv.",
        "Status",
        "VWAP",
        "ST",
        "RVOL",
        "Vol accel",
        "Spread %",
    ]
    assert table.iloc[0]["Conv."] == 70.0
    assert table.iloc[0]["Status"] == "WATCH NOW"
    assert table.iloc[0]["VWAP"] == "above"

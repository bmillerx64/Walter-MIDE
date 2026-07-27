from mide.ui import radar_table, state_sections, summary_reasons


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
        "Phase",
        "Opp.",
        "Conv.",
        "Priority",
        "Status",
        "VWAP",
        "ST",
        "RVOL",
        "Vol accel",
        "Spread %",
    ]
    assert table.iloc[0]["Phase"] == "Emerging"
    assert table.iloc[0]["Conv."] == 70.0
    assert table.iloc[0]["Priority"] == "STRONG"
    assert table.iloc[0]["Status"] == "WATCH NOW"
    assert table.iloc[0]["VWAP"] == "above"


def test_summary_reasons_prioritize_entry_ready_state_over_list_order():
    reasons = summary_reasons(
        sample_record(
            status="Entry Ready",
            candidate_status="Entry Ready",
            reasons=[
                "Above 65 EMA",
                "Higher lows",
                "Fresh SuperTrend flip",
                "Above VWAP",
                "rising RVOL 4.2×",
            ],
            supertrend_flip=True,
            rvol_proxy=4.2,
        )
    )

    assert reasons == [
        "30-second SuperTrend flipped",
        "Above VWAP",
        "RVOL 4.2× and increasing",
    ]


def test_summary_reasons_prioritize_watch_list_state_over_list_order():
    reasons = summary_reasons(
        sample_record(
            status="WATCH NOW",
            candidate_status="Watching",
            reasons=[
                "SuperTrend supportive",
                "flat base with activity expanding",
                "Testing VWAP",
                "rising RVOL 2.8×",
            ],
            vwap_relation="testing",
            rvol_proxy=2.8,
        )
    )

    assert reasons == ["RVOL 2.8× and increasing", "Flat base maintained", "Near VWAP"]


def test_radar_table_preserves_priority_sorted_input_order():
    table = radar_table(
        [
            sample_record(symbol="ROCKET", status="ALERT", conviction_score=60),
            sample_record(symbol="ENTRY", status="Entry Ready", conviction_score=99),
            sample_record(symbol="STRONG", status="WATCH NOW", conviction_score=95),
        ]
    )

    assert table["Symbol"].tolist() == ["ROCKET", "ENTRY", "STRONG"]
    assert table["Priority"].tolist() == ["ROCKET", "ENTRY READY", "STRONG"]


def test_workflow_section_ranks_by_additive_opportunity_score():
    lower = sample_record(
        symbol="LOW", candidate_status="Strengthening", opportunity_score_v2=61
    )
    higher = sample_record(
        symbol="HIGH", candidate_status="Strengthening", opportunity_score_v2=88
    )

    assert [
        item["symbol"] for item in state_sections([lower, higher])["Strengthening"]
    ] == [
        "HIGH",
        "LOW",
    ]

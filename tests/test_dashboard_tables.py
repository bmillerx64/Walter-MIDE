from mide import ui
from mide.ui import (
    mission_control_header_markup,
    opportunity_pulse,
    radar_table,
    state_sections,
    summary_reasons,
    walter_mission_control,
    walter_hot_list,
)


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


def test_hot_list_ranks_by_state_before_dynamic_priority_score():
    records = [
        sample_record(
            symbol="CAND",
            candidate_status="Emerging",
            participation_surge_score=99,
            expansion_quality=99,
        ),
        sample_record(
            symbol="READY",
            candidate_status="Entry Ready",
            participation_surge_score=50,
            expansion_quality=50,
        ),
        sample_record(
            symbol="STR",
            candidate_status="Strengthening",
            participation_surge_score=95,
            expansion_quality=95,
        ),
        sample_record(
            symbol="WATCH",
            candidate_status="Watching",
            participation_surge_score=98,
            expansion_quality=98,
        ),
    ]

    hot = walter_hot_list(records)

    assert [item["symbol"] for item in hot] == ["READY", "STR", "WATCH"]
    assert all(0 <= item["priority_score"] <= 100 for item in hot)


def test_hot_list_fresh_catalyst_can_outweigh_stronger_raw_metrics():
    no_news = sample_record(
        symbol="RAW",
        candidate_status="Strengthening",
        participation_surge_score=95,
        expansion_quality=88,
        vwap_distance_pct=0.2,
        headline="",
        market_dominance_score=0,
    )
    catalyst = sample_record(
        symbol="NEWS",
        candidate_status="Strengthening",
        participation_surge_score=82,
        expansion_quality=79,
        vwap_distance_pct=0.8,
        headline="FDA clearance",
        catalyst_score=10,
        news_age_hours=1,
        market_dominance_score=0,
    )

    hot = walter_hot_list([no_news, catalyst])

    assert [item["symbol"] for item in hot] == ["NEWS", "RAW"]
    assert hot[0]["reasons"][0] == "Fresh news catalyst"


def test_hot_list_excludes_rejected_and_weak_symbols_without_placeholders():
    records = [
        sample_record(symbol="ONLY", candidate_status="Watching"),
        sample_record(
            symbol="REJECT", candidate_status="Emerging", qualified_for_watch=False
        ),
        sample_record(symbol="WEAK", candidate_status="Weakening"),
    ]

    assert [item["symbol"] for item in walter_hot_list(records)] == ["ONLY"]


def test_mission_control_commits_to_one_primary_and_secondary_by_urgency():
    records = [
        sample_record(symbol="MON", candidate_status="Watching", participation_score=95),
        sample_record(symbol="READY", candidate_status="Entry Ready", participation_score=96),
        sample_record(symbol="NEXT", candidate_status="Strengthening", participation_score=92),
    ]

    mission = walter_mission_control(records)

    assert mission["primary"]["symbol"] == "READY"
    assert mission["primary"]["band"] == "trade_soon"
    assert mission["secondary"]["symbol"] == "NEXT"
    assert mission["secondary"]["band"] == "watch_closely"


def test_mission_control_explains_exact_remaining_setup_conditions():
    mission = walter_mission_control(
        [
            sample_record(
                symbol="WAIT",
                candidate_status="Strengthening",
                vwap_relation="above",
                vwap_distance_pct=0.4,
                supertrend_bullish=False,
                supertrend_flip=False,
                participation_score=94,
            )
        ]
    )

    primary = mission["primary"]
    assert primary["status"] == "Ready if candle confirms SuperTrend"
    assert [item["label"] for item in primary["conditions"] if not item["passed"]] == [
        "SuperTrend flip"
    ]


def test_mission_control_separates_extended_symbols_into_ignore():
    mission = walter_mission_control(
        [
            sample_record(symbol="FOCUS", candidate_status="Watching"),
            sample_record(symbol="CHASE", candidate_status="Strengthening", vwap_distance_pct=6.2),
        ]
    )

    assert mission["primary"]["symbol"] == "FOCUS"
    assert [(item["symbol"], item["status"]) for item in mission["ignored"]] == [
        ("CHASE", "Too extended")
    ]


def test_mission_control_header_contains_compact_operational_status():
    markup = mission_control_header_markup(
        live=True,
        market_phase="Live Market",
        market_time="9:31:18 AM EDT",
        symbols_sampled=674,
        prefilter_count=88,
        candidate_count=10,
        focus_count=2,
        escalation_count=1,
        next_scan="00:18",
    )

    assert "Walter • MIDE Radar" in markup
    assert "v3.0 Beta — Mission Control" in markup
    assert "Market Intelligence Decision Engine" in markup
    for value in ("🟢 LIVE", "Live Market", "674", "88", "10", "2", "1", "00:18"):
        assert value in markup


def test_ignore_today_explains_non_actionable_quality():
    mission = walter_mission_control(
        [sample_record(symbol="THIN", candidate_status="Weakening", participation_score=30)]
    )

    assert mission["ignored"][0]["status"] == "Low participation"


def test_opportunity_meter_shows_only_remaining_condition_and_change_flash():
    previous = sample_record(
        candidate_status="Strengthening",
        vwap_relation="below",
        supertrend_bullish=False,
        participation_score=94,
    )
    current = sample_record(
        symbol="WAIT",
        candidate_status="Strengthening",
        vwap_relation="above",
        vwap_distance_pct=0.4,
        supertrend_bullish=False,
        participation_score=94,
        opportunity_pulse_previous=previous,
    )

    markup = ui._mission_target_markup(
        walter_mission_control([current])["primary"], "Primary target"
    )

    assert "Opportunity Meter" in markup
    assert "aria-valuenow='" in markup
    assert "One Thing Left" in markup
    assert "Waiting for SuperTrend flip" in markup
    assert "VWAP reclaim achieved ✓" in markup
    assert "mission-condition-met" in markup
    assert "Ready checklist" not in markup


def test_opportunity_meter_pulses_when_entry_window_first_opens():
    previous = sample_record(
        candidate_status="Strengthening",
        supertrend_bullish=False,
        participation_score=96,
    )
    current = sample_record(
        symbol="OPEN",
        candidate_status="Entry Ready",
        supertrend_bullish=True,
        participation_score=96,
        opportunity_pulse_previous=previous,
    )

    markup = ui._mission_target_markup(
        walter_mission_control([current])["primary"], "Primary target"
    )

    assert "ENTRY WINDOW OPEN" in markup
    assert "entry-window-pulse" in markup
    assert "Thing Left" not in markup


def test_hot_list_renders_priority_score_as_confidence_meter(monkeypatch):
    rendered = []

    class Column:
        def markdown(self, body, **kwargs):
            rendered.append(body)

    monkeypatch.setattr(ui.st, "subheader", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        ui.st, "columns", lambda count: [Column() for _ in range(count)]
    )
    monkeypatch.setattr(
        ui,
        "walter_hot_list",
        lambda _records: [
            {
                "symbol": "ENTX",
                "state": "Strengthening",
                "priority_score": 82,
                "reasons": ["Fresh news catalyst", "Near VWAP (+0.2%)"],
                "limiting_factor": "VWAP pullback",
                "pulse": {"label": "ACCELERATING", "color": "green", "delta": 8},
            }
        ],
    )

    ui.render_walter_hot_list([{}])

    card = rendered[0]
    assert "Priority Score" not in card
    assert "Confidence" in card
    assert "aria-valuenow='82'" in card
    assert "--confidence:82%" in card
    assert "82%" in card
    assert ">HIGH<" in card
    assert "hot-confidence-green" in card
    assert "ACCELERATING" in card
    assert "+8" in card
    assert "pulse-green" in card
    assert ">Strengthening<" not in card


def test_opportunity_pulse_compares_evidence_without_changing_priority():
    previous = sample_record(
        participation_surge_score=60,
        expansion_quality=55,
        conviction_v2_score=65,
    )
    current = sample_record(
        participation_surge_score=68,
        expansion_quality=62,
        conviction_v2_score=67,
        opportunity_pulse_previous=previous,
    )

    status_before = current["status"]

    assert opportunity_pulse(current)["label"] == "ACCELERATING"
    assert current["status"] == status_before


def test_opportunity_pulse_flags_broad_deterioration_and_conviction_loss():
    previous = sample_record(
        participation_surge_score=75,
        expansion_quality=70,
        conviction_v2_score=80,
    )
    fading = sample_record(
        participation_surge_score=67,
        expansion_quality=64,
        conviction_v2_score=79,
        opportunity_pulse_previous=previous,
    )
    conviction_loss = sample_record(
        participation_surge_score=76,
        expansion_quality=71,
        conviction_v2_score=74,
        opportunity_pulse_previous=previous,
    )

    assert opportunity_pulse(fading)["label"] == "LOSING MOMENTUM"
    assert opportunity_pulse(conviction_loss)["label"] == "LOSING MOMENTUM"


def test_opportunity_pulse_is_stable_without_prior_scan_or_meaningful_change():
    assert opportunity_pulse(sample_record()) == {
        "label": "STABLE",
        "color": "yellow",
        "delta": 0,
    }
    previous = sample_record(participation_surge_score=60, expansion_quality=55)
    current = sample_record(
        participation_surge_score=62,
        expansion_quality=54,
        opportunity_pulse_previous=previous,
    )
    assert opportunity_pulse(current)["label"] == "STABLE"


def test_confidence_levels_match_display_thresholds():
    assert ui._confidence_presentation(100) == ("ELITE", "green")
    assert ui._confidence_presentation(90) == ("ELITE", "green")
    assert ui._confidence_presentation(89) == ("HIGH", "green")
    assert ui._confidence_presentation(80) == ("HIGH", "green")
    assert ui._confidence_presentation(79) == ("GOOD", "yellow")
    assert ui._confidence_presentation(70) == ("GOOD", "yellow")
    assert ui._confidence_presentation(69) == ("DEVELOPING", "yellow")
    assert ui._confidence_presentation(60) == ("DEVELOPING", "yellow")
    assert ui._confidence_presentation(59) == ("EARLY", "red")


def test_opportunity_card_makes_current_trend_history_and_action_context_explicit(
    monkeypatch,
):
    rendered = []
    monkeypatch.setattr(ui.st, "markdown", lambda body, **kwargs: rendered.append(body))

    ui.opportunity_card(
        sample_record(
            conviction_v2_score=58,
            conviction_delta=-12,
            conviction_trend="Falling",
            conviction_history=[70, 58],
            conviction_change_reasons=[
                "Participation faded",
                "Trend confirmation weakened",
            ],
            tradeability="Wait",
            candidate_status="Strengthening",
        )
    )

    card = rendered[-1]
    assert "NOW — current scan" in card
    assert "TREND — compared with previous scan" in card
    assert "Conviction -12.0" in card
    assert "ACTION — Walter's recommendation" in card
    assert "Current Evidence" in card
    assert "Participation Surge" in card
    assert "FAIL (Requires 72)" in card
    assert "Participation faded" not in card
    assert "Why this scan promoted it" not in card

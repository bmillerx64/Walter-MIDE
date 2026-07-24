from mide.scoring import Evidence, score


def base(**updates):
    values = dict(
        symbol="TEST",
        price=0.50,
        pct_change=20,
        volume=5_000_000,
        dollar_volume=2_500_000,
        spread_pct=1.0,
        vwap_relation="above",
        vwap_distance_pct=0.2,
        supertrend_bullish=True,
        supertrend_flip=True,
        ema65_relation="above",
        ema65_distance_pct=0.3,
        volume_acceleration=2.0,
        green_volume_ratio=2.0,
        rvol_proxy=5.0,
        higher_lows=True,
        near_hod=True,
        catalyst_score=10,
        headline="Company wins contract",
        news_age_hours=2,
        risk_flags=[],
        timeframe_confirmations=4,
        discovery_reasons=["market mover"],
    )
    values.update(updates)
    return Evidence(**values)


def test_aligned_setup_is_elevated():
    result = score(base())
    assert result.status in {"MONITOR", "WATCH NOW", "ALERT", "EXCEPTIONAL"}
    assert result.opportunity_score >= 60


def test_offering_is_pass():
    result = score(
        base(
            headline="Company announces registered direct offering",
            catalyst_score=-28,
            risk_flags=["registered direct", "offering"],
        )
    )
    assert result.status == "PASS"


def test_no_news_can_still_elevate():
    result = score(base(headline="", catalyst_score=0, news_age_hours=None))
    assert result.status in {"MONITOR", "WATCH NOW", "ALERT", "EXCEPTIONAL"}


def test_major_volume_scores_higher_than_modest_volume():
    modest = score(base(volume=500_000, dollar_volume=250_000, rvol_proxy=2.0))
    major = score(base(volume=50_000_000, dollar_volume=25_000_000, rvol_proxy=8.0))
    assert major.participation_score > modest.participation_score + 15
    assert major.attention_score > modest.attention_score
    assert major.participation_tier in {"EXCEPTIONAL", "DOMINANT"}


def test_historical_strength_and_current_momentum_are_independent():
    faded_leader = score(
        base(
            volume=80_000_000,
            dollar_volume=120_000_000,
            pct_change=250,
            rvol_proxy=12,
            volume_acceleration=0.8,
            green_volume_ratio=0.8,
            vwap_relation="below",
            vwap_distance_pct=-4,
            supertrend_bullish=False,
            supertrend_flip=False,
            ema65_relation="below",
            higher_lows=False,
            near_hod=False,
            timeframe_confirmations=0,
        )
    )
    fresh_breakout = score(
        base(
            volume=900_000,
            dollar_volume=900_000,
            pct_change=8,
            rvol_proxy=2.2,
            volume_acceleration=2.5,
            green_volume_ratio=2.0,
            supertrend_flip=True,
            timeframe_confirmations=4,
        )
    )

    assert faded_leader.historical_strength > fresh_breakout.historical_strength
    assert fresh_breakout.current_momentum > faded_leader.current_momentum


def test_attention_ranking_uses_current_momentum_before_historical_strength():
    from mide.discovery import apply_attention_ranking

    records = [
        {
            "symbol": "HIST",
            "volume": 80_000_000,
            "dollar_volume": 120_000_000,
            "pct_change": 250,
            "rvol_proxy": 12,
            "opportunity_score": 35,
            "current_momentum": 35,
            "historical_strength": 96,
            "participation_score": 96,
            "status": "ALERT",
            "reasons": [],
        },
        {
            "symbol": "NOW",
            "volume": 900_000,
            "dollar_volume": 900_000,
            "pct_change": 8,
            "rvol_proxy": 2.2,
            "opportunity_score": 91,
            "current_momentum": 91,
            "historical_strength": 35,
            "participation_score": 35,
            "status": "MONITOR",
            "reasons": [],
        },
    ]

    ranked = apply_attention_ranking(records)

    assert ranked[0]["symbol"] == "NOW"
    assert ranked[0]["current_momentum"] > ranked[1]["current_momentum"]
    assert ranked[1]["historical_strength"] > ranked[0]["historical_strength"]


def test_dominance_is_nonzero_and_ranks_leader():
    from mide.discovery import apply_attention_ranking

    records = [
        {
            "symbol": "LEAD",
            "volume": 30_000_000,
            "dollar_volume": 15_000_000,
            "pct_change": 40,
            "rvol_proxy": 8,
            "opportunity_score": 90,
            "participation_score": 94,
            "status": "ALERT",
            "reasons": [],
        },
        {
            "symbol": "OTHER",
            "volume": 3_000_000,
            "dollar_volume": 1_000_000,
            "pct_change": 10,
            "rvol_proxy": 2,
            "opportunity_score": 65,
            "participation_score": 55,
            "status": "MONITOR",
            "reasons": [],
        },
    ]
    ranked = apply_attention_ranking(records)
    assert ranked[0]["symbol"] == "LEAD"
    assert ranked[0]["market_dominance_score"] > ranked[1]["market_dominance_score"] > 0


def test_scanner_v2_rewards_developing_momentum_without_completed_setup():
    from mide.scanner_v2 import apply_scanner_v2

    record = {
        **base(
            vwap_relation="below",
            supertrend_bullish=False,
            supertrend_flip=False,
            ema65_relation="below",
            timeframe_confirmations=0,
        ).__dict__,
        "opportunity_score": 48,
        "participation_score": 72,
        "status": "PASS",
        "timeframes": {},
        "reasons": [],
        "cautions": [],
    }
    ranked = apply_scanner_v2([record], {})
    assert ranked[0]["candidate_status"] in {"Watching", "Emerging", "Strengthening"}
    assert "accelerating volume" in " ".join(ranked[0]["reasons"])


def test_scanner_v2_alerts_only_when_entering_or_advancing_watch_state():
    from mide.scanner_v2 import apply_scanner_v2

    prior = {
        "TEST": {
            "candidate_status": "Watching",
            "scanner_v2_score": 40,
            "volume": 1_000_000,
            "dollar_volume": 500_000,
            "rvol_proxy": 1.5,
            "opportunity_score": 45,
            "vwap_relation": "below",
        }
    }
    record = {
        **base(timeframe_confirmations=3).__dict__,
        "opportunity_score": 70,
        "participation_score": 80,
        "status": "MONITOR",
        "timeframes": {
            "1m": {"above_vwap": True, "supertrend": True},
            "3m": {"above_vwap": True, "supertrend": True},
            "5m": {"above_vwap": True, "supertrend": True},
        },
        "reasons": [],
        "cautions": [],
    }
    ranked = apply_scanner_v2([record], prior)
    assert ranked[0]["candidate_status"] in {"Strengthening", "Entry Ready"}
    assert ranked[0]["advanced_state"] is True
    assert ranked[0]["alert_event"] is True


def test_scanner_v2_promotion_delta_marks_state_advancement_without_behavior_change():
    from datetime import datetime, timezone

    from mide.scanner_v2 import apply_scanner_v2

    prior_entered = "2026-07-23T14:20:00+00:00"
    prior = {
        "TEST": {
            "candidate_status": "Watching",
            "state_entered_at": prior_entered,
            "transition_history": [{"state": "Watching", "entered_at": prior_entered}],
            "scanner_v2_score": 42,
            "volume": 900_000,
            "dollar_volume": 450_000,
            "rvol_proxy": 1.8,
            "opportunity_score": 45,
            "vwap_relation": "below",
        }
    }
    record = {
        **base(timeframe_confirmations=3).__dict__,
        "opportunity_score": 72,
        "participation_score": 82,
        "status": "MONITOR",
        "timeframes": {
            "1m": {"above_vwap": True, "supertrend": True},
            "3m": {"above_vwap": True, "supertrend": True},
            "5m": {"above_vwap": True, "supertrend": True},
        },
        "reasons": [],
        "cautions": [],
    }

    ranked = apply_scanner_v2(
        [record], prior, scan_time=datetime(2026, 7, 23, 14, 31, tzinfo=timezone.utc)
    )

    assert ranked[0]["previous_candidate_status"] == "Watching"
    assert ranked[0]["candidate_status"] in {"Strengthening", "Entry Ready"}
    assert ranked[0]["advanced_state"] is True
    assert ranked[0]["entered_watchlist"] is False
    assert ranked[0]["alert_event"] is True
    assert ranked[0]["state_entered_at"] == "2026-07-23T14:31:00+00:00"
    assert ranked[0]["transition_history"][0] == {
        "state": "Watching",
        "entered_at": prior_entered,
    }
    assert ranked[0]["transition_history"][-1] == {
        "state": ranked[0]["candidate_status"],
        "entered_at": "2026-07-23T14:31:00+00:00",
    }


def test_strengthening_promotion_records_changed_conditions():
    from mide.scanner_v2 import apply_scanner_v2

    prior = {
        "TEST": {
            "candidate_status": "Emerging",
            "scanner_v2_score": 55,
            "volume": 450_000,
            "dollar_volume": 200_000,
            "rvol_proxy": 1.2,
            "opportunity_score": 55,
            "vwap_relation": "below",
            "supertrend_flip": False,
            "timeframes": {"1m": {"above_vwap": True, "supertrend": False}},
        }
    }
    record = {
        **base(
            vwap_relation="above", supertrend_flip=True, timeframe_confirmations=2
        ).__dict__,
        "volume": 900_000,
        "dollar_volume": 300_000,
        "rvol_proxy": 1.8,
        "opportunity_score": 72,
        "status": "MONITOR",
        "timeframes": {
            "1m": {"above_vwap": True, "supertrend": True},
            "3m": {"above_vwap": True, "supertrend": False},
        },
        "reasons": [],
        "cautions": [],
    }

    from datetime import datetime, timezone

    ranked = apply_scanner_v2(
        [record], prior, scan_time=datetime(2026, 7, 23, 13, 45, tzinfo=timezone.utc)
    )

    assert ranked[0]["candidate_status"] in {"Strengthening", "Entry Ready"}
    assert ranked[0]["advanced_state"] is True
    assert ranked[0]["promotion_trigger"] == "VWAP reclaim"
    assert "30s ST flip" in ranked[0]["promotion_condition_changes"]
    assert "1m ST confirmation" in ranked[0]["promotion_condition_changes"]
    assert "volume threshold crossed" in ranked[0]["promotion_condition_changes"]


def test_unchanged_strengthening_state_does_not_record_promotion_trigger():
    from mide.scanner_v2 import apply_scanner_v2

    prior = {
        "TEST": {
            "candidate_status": "Strengthening",
            "scanner_v2_score": 70,
            "volume": 900_000,
            "dollar_volume": 500_000,
            "rvol_proxy": 2.0,
            "opportunity_score": 70,
            "vwap_relation": "above",
            "supertrend_flip": True,
        }
    }
    record = {
        **base().__dict__,
        "opportunity_score": 72,
        "status": "MONITOR",
        "timeframes": {"1m": {"above_vwap": True, "supertrend": True}},
        "reasons": [],
        "cautions": [],
    }

    ranked = apply_scanner_v2([record], prior)

    assert ranked[0]["candidate_status"] in {"Strengthening", "Entry Ready"}
    assert ranked[0]["promotion_condition_changes"] == []
    assert ranked[0]["promotion_trigger"] is None


def test_scanner_v2_no_promotion_delta_when_state_is_unchanged():
    from datetime import datetime, timezone

    from mide.scanner_v2 import apply_scanner_v2

    entered = "2026-07-23T14:20:00+00:00"
    prior = {
        "TEST": {
            "candidate_status": "Strengthening",
            "state_entered_at": entered,
            "transition_history": [{"state": "Strengthening", "entered_at": entered}],
            "scanner_v2_score": 70,
            "volume": 1_000_000,
            "dollar_volume": 600_000,
            "rvol_proxy": 2.0,
            "opportunity_score": 70,
            "vwap_relation": "below",
        }
    }
    record = {
        **base(
            vwap_relation="below", supertrend_bullish=False, supertrend_flip=False
        ).__dict__,
        "opportunity_score": 72,
        "status": "MONITOR",
        "timeframes": {},
        "reasons": [],
        "cautions": [],
    }

    ranked = apply_scanner_v2(
        [record], prior, scan_time=datetime(2026, 7, 23, 14, 31, tzinfo=timezone.utc)
    )

    assert ranked[0]["candidate_status"] == "Strengthening"
    assert ranked[0]["advanced_state"] is False
    assert ranked[0]["entered_watchlist"] is False
    assert ranked[0]["alert_event"] is False
    assert ranked[0]["state_entered_at"] == entered
    assert ranked[0]["state_elapsed_seconds"] == 660
    assert ranked[0]["transition_history"] == prior["TEST"]["transition_history"]


def test_entry_ready_allows_supportive_timeframes_without_all_green():
    from mide.scanner_v2 import apply_scanner_v2

    prior = {
        "TEST": {
            "candidate_status": "Strengthening",
            "scanner_v2_score": 68,
            "volume": 1_000_000,
            "dollar_volume": 500_000,
            "rvol_proxy": 2.0,
            "opportunity_score": 68,
            "vwap_relation": "testing",
        }
    }
    record = {
        **base(timeframe_confirmations=1).__dict__,
        "volume": 1_200_000,
        "dollar_volume": 650_000,
        "opportunity_score": 74,
        "participation_score": 80,
        "status": "MONITOR",
        "supertrend_30s_flip": True,
        "timeframes": {
            "1m": {
                "above_vwap": True,
                "supertrend": False,
                "near_supertrend_flip": True,
            },
            "3m": {"above_vwap": True, "supertrend": True},
        },
        "reasons": [],
        "cautions": [],
    }

    ranked = apply_scanner_v2([record], prior)
    assert ranked[0]["candidate_status"] == "Entry Ready"
    assert ranked[0]["promotion_trigger"] in {"VWAP reclaim", "30s ST flip"}
    assert "30s ST flip" in ranked[0]["promotion_condition_changes"]


def test_entry_ready_state_uses_chart_preparation_requirements_only():
    from mide.scanner_v2 import apply_scanner_v2

    prior = {
        "TEST": {
            "candidate_status": "Strengthening",
            "scanner_v2_score": 95,
            "opportunity_score": 95,
        }
    }
    record = {
        **base(
            timeframe_confirmations=1, volume_acceleration=0.8, rvol_proxy=1.0
        ).__dict__,
        "volume": 900_000,
        "dollar_volume": 450_000,
        "opportunity_score": 52,
        "participation_score": 55,
        "status": "MONITOR",
        "supertrend_30s_flip": True,
        "vwap_relation": "above",
        "timeframes": {
            "1m": {
                "above_vwap": True,
                "supertrend": False,
                "near_supertrend_flip": True,
            },
            "3m": {
                "above_vwap": True,
                "supertrend": False,
                "very_close_to_flipping": True,
            },
        },
        "reasons": [],
        "cautions": [],
    }

    ranked = apply_scanner_v2([record], prior)
    assert ranked[0]["candidate_status"] == "Rejected – No Participation"
    assert ranked[0]["qualified_for_ranking"] is False
    assert ranked[0]["rejection_reason"] == "No Participation"


def test_scanner_v2_timer_starts_when_entering_timed_state():
    from datetime import datetime, timezone

    from mide.scanner_v2 import apply_scanner_v2

    scan_time = datetime(2026, 7, 23, 14, 30, tzinfo=timezone.utc)
    record = {
        **base(
            vwap_relation="below", supertrend_bullish=False, supertrend_flip=False
        ).__dict__,
        "opportunity_score": 55,
        "status": "PASS",
        "timeframes": {},
        "reasons": [],
        "cautions": [],
    }

    ranked = apply_scanner_v2([record], {}, scan_time=scan_time)

    assert ranked[0]["candidate_status"] == "Strengthening"
    assert ranked[0]["state_entered_at"] == "2026-07-23T14:30:00+00:00"
    assert ranked[0]["state_elapsed_seconds"] == 0


def test_scanner_v2_timer_resets_on_state_change():
    from datetime import datetime, timezone

    from mide.scanner_v2 import apply_scanner_v2

    prior_entered = "2026-07-23T14:20:00+00:00"
    scan_time = datetime(2026, 7, 23, 14, 30, tzinfo=timezone.utc)
    prior = {
        "TEST": {
            "candidate_status": "Emerging",
            "state_entered_at": prior_entered,
            "scanner_v2_score": 55,
            "opportunity_score": 55,
            "volume": 1_000_000,
            "dollar_volume": 600_000,
            "rvol_proxy": 2.0,
        }
    }
    record = {
        **base(
            vwap_relation="below",
            supertrend_bullish=True,
            supertrend_flip=False,
            timeframe_confirmations=3,
        ).__dict__,
        "opportunity_score": 75,
        "status": "MONITOR",
        "timeframes": {
            "1m": {"above_vwap": True, "supertrend": True},
            "3m": {"above_vwap": False, "supertrend": True},
            "5m": {"above_vwap": True, "supertrend": True},
        },
        "reasons": [],
        "cautions": [],
    }

    ranked = apply_scanner_v2([record], prior, scan_time=scan_time)

    assert ranked[0]["candidate_status"] == "Strengthening"
    assert ranked[0]["state_entered_at"] == "2026-07-23T14:30:00+00:00"
    assert ranked[0]["state_elapsed_seconds"] == 0


def test_scanner_v2_timer_continues_across_automatic_scans():
    from datetime import datetime, timezone

    from mide.scanner_v2 import apply_scanner_v2

    prior = {
        "TEST": {
            "candidate_status": "Strengthening",
            "state_entered_at": "2026-07-23T14:30:00+00:00",
            "scanner_v2_score": 55,
            "opportunity_score": 55,
            "volume": 1_000_000,
            "dollar_volume": 600_000,
            "rvol_proxy": 2.0,
        }
    }
    record = {
        **base(
            vwap_relation="below", supertrend_bullish=False, supertrend_flip=False
        ).__dict__,
        "opportunity_score": 55,
        "status": "PASS",
        "timeframes": {},
        "reasons": [],
        "cautions": [],
    }

    ranked = apply_scanner_v2(
        [record],
        prior,
        scan_time=datetime(2026, 7, 23, 14, 32, 15, tzinfo=timezone.utc),
    )

    assert ranked[0]["candidate_status"] == "Strengthening"
    assert ranked[0]["state_entered_at"] == "2026-07-23T14:30:00+00:00"
    assert ranked[0]["state_elapsed_seconds"] == 135


def test_scanner_v2_sorts_newest_promotions_within_state():
    from datetime import datetime, timezone

    from mide.scanner_v2 import apply_scanner_v2

    older = {
        **base(
            symbol="OLD",
            vwap_relation="below",
            supertrend_bullish=False,
            supertrend_flip=False,
        ).__dict__,
        "opportunity_score": 55,
        "status": "PASS",
        "timeframes": {},
        "reasons": [],
        "cautions": [],
    }
    newer = {
        **base(
            symbol="NEW",
            vwap_relation="below",
            supertrend_bullish=False,
            supertrend_flip=False,
        ).__dict__,
        "opportunity_score": 55,
        "status": "PASS",
        "timeframes": {},
        "reasons": [],
        "cautions": [],
    }
    prior = {
        "OLD": {
            "candidate_status": "Strengthening",
            "state_entered_at": "2026-07-23T14:20:00+00:00",
            "scanner_v2_score": 55,
            "opportunity_score": 55,
            "volume": 1_000_000,
            "dollar_volume": 600_000,
            "rvol_proxy": 2.0,
        },
        "NEW": {
            "candidate_status": "Strengthening",
            "state_entered_at": "2026-07-23T14:29:00+00:00",
            "scanner_v2_score": 55,
            "opportunity_score": 55,
            "volume": 1_000_000,
            "dollar_volume": 600_000,
            "rvol_proxy": 2.0,
        },
    }

    ranked = apply_scanner_v2(
        [older, newer],
        prior,
        scan_time=datetime(2026, 7, 23, 14, 30, tzinfo=timezone.utc),
    )

    assert [record["symbol"] for record in ranked] == ["NEW", "OLD"]


def test_scanner_v2_sort_normalizes_mixed_prior_state_entered_values():
    from datetime import datetime, timezone

    from mide.scanner_v2 import apply_scanner_v2

    string_record = {
        **base(
            symbol="STRING",
            vwap_relation="below",
            supertrend_bullish=False,
            supertrend_flip=False,
        ).__dict__,
        "opportunity_score": 55,
        "status": "PASS",
        "timeframes": {},
        "reasons": [],
        "cautions": [],
    }
    datetime_record = {
        **base(
            symbol="DATETIME",
            vwap_relation="below",
            supertrend_bullish=False,
            supertrend_flip=False,
        ).__dict__,
        "opportunity_score": 55,
        "status": "PASS",
        "timeframes": {},
        "reasons": [],
        "cautions": [],
    }
    prior = {
        "STRING": {
            "candidate_status": "Strengthening",
            "state_entered_at": "2026-07-23T14:29:00+00:00",
            "scanner_v2_score": "55",
        },
        "DATETIME": {
            "candidate_status": "Strengthening",
            "state_entered_at": datetime(2026, 7, 23, 14, 30, tzinfo=timezone.utc),
            "scanner_v2_score": None,
        },
    }

    ranked = apply_scanner_v2(
        [string_record, datetime_record],
        prior,
        scan_time=datetime(2026, 7, 23, 14, 32, tzinfo=timezone.utc),
    )

    assert [record["symbol"] for record in ranked] == ["DATETIME", "STRING"]


def test_scanner_v2_transition_history_records_state_changes():
    from datetime import datetime, timezone

    from mide.scanner_v2 import apply_scanner_v2

    emerging_entered = "2026-07-23T14:30:00+00:00"
    prior = {
        "TEST": {
            "candidate_status": "Emerging",
            "state_entered_at": emerging_entered,
            "transition_history": [
                {"state": "Emerging", "entered_at": emerging_entered}
            ],
            "scanner_v2_score": 55,
            "opportunity_score": 55,
            "volume": 1_000_000,
            "dollar_volume": 600_000,
            "rvol_proxy": 2.0,
        }
    }
    record = {
        **base(
            vwap_relation="below",
            supertrend_bullish=True,
            supertrend_flip=False,
            timeframe_confirmations=3,
        ).__dict__,
        "opportunity_score": 75,
        "status": "MONITOR",
        "timeframes": {
            "1m": {"above_vwap": True, "supertrend": True},
            "3m": {"above_vwap": False, "supertrend": True},
            "5m": {"above_vwap": True, "supertrend": True},
        },
        "reasons": [],
        "cautions": [],
    }

    ranked = apply_scanner_v2(
        [record],
        prior,
        scan_time=datetime(2026, 7, 23, 14, 31, 42, tzinfo=timezone.utc),
    )

    assert ranked[0]["transition_history"] == [
        {"state": "Emerging", "entered_at": emerging_entered},
        {"state": "Strengthening", "entered_at": "2026-07-23T14:31:42+00:00"},
    ]


def test_scanner_v2_transition_history_updates_when_state_does_not_change():
    from datetime import datetime, timezone

    from mide.scanner_v2 import apply_scanner_v2

    entered = "2026-07-23T14:30:00+00:00"
    prior = {
        "TEST": {
            "candidate_status": "Strengthening",
            "state_entered_at": entered,
            "transition_history": [
                {"state": "Emerging", "entered_at": "2026-07-23T14:28:00+00:00"},
                {"state": "Strengthening", "entered_at": entered},
            ],
            "scanner_v2_score": 55,
            "opportunity_score": 55,
            "volume": 1_000_000,
            "dollar_volume": 600_000,
            "rvol_proxy": 2.0,
        }
    }
    record = {
        **base(
            vwap_relation="below", supertrend_bullish=False, supertrend_flip=False
        ).__dict__,
        "opportunity_score": 55,
        "status": "PASS",
        "timeframes": {},
        "reasons": [],
        "cautions": [],
    }

    ranked = apply_scanner_v2(
        [record],
        prior,
        scan_time=datetime(2026, 7, 23, 14, 32, 15, tzinfo=timezone.utc),
    )

    assert ranked[0]["candidate_status"] == "Strengthening"
    assert ranked[0]["state_entered_at"] == entered
    assert ranked[0]["state_elapsed_seconds"] == 135
    assert ranked[0]["transition_history"] == prior["TEST"]["transition_history"]


def test_scanner_v2_transition_history_resets_after_symbol_reenters_scanner():
    from datetime import datetime, timezone

    from mide.scanner_v2 import apply_scanner_v2

    prior = {
        "TEST": {
            "candidate_status": "Removed",
            "state_entered_at": None,
            "transition_history": [
                {"state": "Emerging", "entered_at": "2026-07-23T14:20:00+00:00"},
                {"state": "Strengthening", "entered_at": "2026-07-23T14:21:00+00:00"},
            ],
            "scanner_v2_score": 20,
            "opportunity_score": 20,
            "volume": 40_000,
            "dollar_volume": 40_000,
            "rvol_proxy": 1.0,
        }
    }
    record = {
        **base(
            vwap_relation="below", supertrend_bullish=False, supertrend_flip=False
        ).__dict__,
        "opportunity_score": 55,
        "status": "PASS",
        "timeframes": {},
        "reasons": [],
        "cautions": [],
    }

    ranked = apply_scanner_v2(
        [record], prior, scan_time=datetime(2026, 7, 23, 14, 35, tzinfo=timezone.utc)
    )

    assert ranked[0]["candidate_status"] == "Strengthening"
    assert ranked[0]["transition_history"] == [
        {"state": "Strengthening", "entered_at": "2026-07-23T14:35:00+00:00"}
    ]


def test_strengthening_diagnostics_records_first_rejection_rule():
    from mide.scanner_v2 import apply_scanner_v2, strengthening_diagnostics

    accepted = {
        **base().__dict__,
        "opportunity_score": 80,
        "status": "MONITOR",
        "timeframes": {"1m": {"above_vwap": True, "supertrend": True}},
        "reasons": [],
        "cautions": [],
    }
    rejected = {
        **base(
            symbol="LOWRVOL",
            volume=1_000,
            dollar_volume=250_000,
            rvol_proxy=1.0,
            volume_acceleration=1.0,
            higher_lows=False,
            ema65_relation="below",
        ).__dict__,
        "opportunity_score": 45,
        "status": "PASS",
        "timeframes": {"1m": {"above_vwap": True, "supertrend": True}},
        "reasons": [],
        "cautions": [],
    }

    ranked = apply_scanner_v2([accepted, rejected], {})
    diagnostics = strengthening_diagnostics(ranked)
    lowrvol = next(
        item for item in diagnostics["decisions"] if item["symbol"] == "LOWRVOL"
    )

    assert diagnostics["candidates_discovered"] == 2
    assert diagnostics["candidates_rejected"] == 1
    assert diagnostics["rejected_by_rule"]["RVOL"] == 1
    assert lowrvol["status"] == "Rejected from Strengthening"
    assert lowrvol["first_rejection_rule"] == "RVOL"
    assert [check["rule"] for check in lowrvol["checks"]][:2] == ["News", "RVOL"]
    assert lowrvol["checks"][0]["passed"] is True
    assert lowrvol["checks"][1]["passed"] is False


def test_scanner_v2_blocks_strengthening_when_well_below_vwap():
    from mide.scanner_v2 import apply_scanner_v2, strengthening_diagnostics

    record = {
        **base(
            symbol="DEEP",
            vwap_relation="below",
            vwap_distance_pct=-4.0,
            supertrend_bullish=True,
            supertrend_flip=True,
            volume_acceleration=3.0,
            rvol_proxy=7.0,
        ).__dict__,
        "volume": 50_000_000,
        "dollar_volume": 25_000_000,
        "opportunity_score": 90,
        "status": "ALERT",
        "timeframes": {
            "1m": {"above_vwap": True, "supertrend": True},
            "3m": {"above_vwap": True, "supertrend": True},
        },
        "reasons": [],
        "cautions": [],
    }

    ranked = apply_scanner_v2([record], {})
    decision = strengthening_diagnostics(ranked)["decisions"][0]

    assert ranked[0]["candidate_status"] == "Emerging"
    assert decision["first_rejection_rule"] == "VWAP"
    assert decision["first_rejection_bucket"] == "Below VWAP"


def test_scanner_v2_allows_strengthening_near_vwap():
    from mide.scanner_v2 import apply_scanner_v2

    record = {
        **base(
            symbol="NEAR",
            vwap_relation="below",
            vwap_distance_pct=-0.8,
            supertrend_bullish=True,
            supertrend_flip=True,
            volume_acceleration=3.0,
            rvol_proxy=7.0,
        ).__dict__,
        "opportunity_score": 90,
        "status": "ALERT",
        "timeframes": {
            "1m": {"above_vwap": True, "supertrend": True},
            "3m": {"above_vwap": True, "supertrend": True},
        },
        "reasons": [],
        "cautions": [],
    }

    ranked = apply_scanner_v2([record], {})

    assert ranked[0]["candidate_status"] == "Strengthening"


def test_scanner_v2_exports_strengthening_diagnostics_for_startup_import():
    from mide.scanner_v2 import strengthening_diagnostics

    assert callable(strengthening_diagnostics)
    assert (
        "strengthening_diagnostics"
        in __import__("mide.scanner_v2", fromlist=["__all__"]).__all__
    )


def test_scanner_v2_prioritizes_tmng_vwap_st_volume_strengthening(caplog):
    from datetime import datetime, timezone
    import logging

    from mide.scanner_v2 import apply_scanner_v2

    prior = {
        "TMNG": {
            "candidate_status": "Emerging",
            "scanner_v2_score": 54,
            "volume": 620_000,
            "dollar_volume": 310_000,
            "rvol_proxy": 1.7,
            "volume_acceleration": 1.1,
            "opportunity_score": 50,
            "vwap_relation": "below",
            "supertrend_flip": False,
        }
    }
    tmng = {
        **base(
            symbol="TMNG",
            vwap_relation="testing",
            vwap_distance_pct=-0.1,
            supertrend_bullish=True,
            supertrend_flip=True,
            ema65_relation="below",
            higher_lows=False,
            headline="",
            catalyst_score=0,
            news_age_hours=None,
            pct_change=3.2,
            volume_acceleration=2.4,
            rvol_proxy=2.1,
        ).__dict__,
        "volume": 780_000,
        "dollar_volume": 390_000,
        "opportunity_score": 52,
        "participation_score": 45,
        "market_dominance_score": 20,
        "status": "MONITOR",
        "timeframes": {
            "1m": {"above_vwap": True, "supertrend": True},
            "3m": {"above_vwap": True, "supertrend": True},
        },
        "reasons": [],
        "cautions": [],
    }
    secondary = {
        **base(
            symbol="BIGV",
            vwap_relation="below",
            vwap_distance_pct=-4.0,
            supertrend_bullish=False,
            supertrend_flip=False,
            pct_change=48,
            volume_acceleration=1.3,
            rvol_proxy=9.0,
        ).__dict__,
        "volume": 60_000_000,
        "dollar_volume": 30_000_000,
        "opportunity_score": 95,
        "participation_score": 98,
        "market_dominance_score": 99,
        "status": "ALERT",
        "timeframes": {},
        "reasons": [],
        "cautions": [],
    }

    with caplog.at_level(logging.INFO, logger="mide.scanner_v2"):
        ranked = apply_scanner_v2(
            [secondary, tmng],
            prior,
            scan_time=datetime(2026, 7, 23, 14, 35, tzinfo=timezone.utc),
        )

    tmng_ranked = next(record for record in ranked if record["symbol"] == "TMNG")
    secondary_ranked = next(record for record in ranked if record["symbol"] == "BIGV")

    assert tmng_ranked["candidate_status"] == "Strengthening"
    assert tmng_ranked["scanner_v2_score"] > secondary_ranked["scanner_v2_score"]
    assert tmng_ranked["strengthening_promotion_diagnostic"] == {
        "vwap_relationship": "testing",
        "supertrend_30s_state": "flipped green",
        "supertrend_1m_state": "green",
        "supertrend_3m_state": "green",
        "volume_acceleration": 2.4,
        "final_weighted_score": tmng_ranked["scanner_v2_score"],
    }
    assert "Strengthening promotion TMNG" in caplog.text
    assert "VWAP=testing" in caplog.text
    assert "30s ST=flipped green" in caplog.text
    assert "volume acceleration=2.4" in caplog.text


def test_strengthening_vwap_gate_uses_current_intraday_vwap_values():
    from mide.scanner_v2 import apply_scanner_v2, strengthening_diagnostics

    def candidate(symbol, price, vwap):
        return {
            **base(
                symbol=symbol,
                price=price,
                vwap_relation="above",  # stale label must not control the gate
                vwap_distance_pct=25.0,  # stale percentage must not control the gate
                supertrend_bullish=True,
                supertrend_flip=True,
                volume_acceleration=3.0,
                rvol_proxy=7.0,
            ).__dict__,
            "vwap_value": vwap,
            "vwap_bar_timeframe_source": "test 1Min current-session bars",
            "volume": 50_000_000,
            "dollar_volume": 25_000_000,
            "opportunity_score": 90,
            "status": "ALERT",
            "timeframes": {
                "1m": {"above_vwap": True, "supertrend": True},
                "3m": {"above_vwap": True, "supertrend": True},
            },
            "reasons": [],
            "cautions": [],
        }

    ranked = apply_scanner_v2(
        [
            candidate("DEEP", 97.0, 100.0),
            candidate("NEAR", 99.5, 100.0),
            candidate("ABOVE", 101.0, 100.0),
        ],
        {},
    )
    by_symbol = {record["symbol"]: record for record in ranked}
    decisions = {
        item["symbol"]: item for item in strengthening_diagnostics(ranked)["decisions"]
    }

    assert by_symbol["DEEP"]["candidate_status"] != "Strengthening"
    assert decisions["DEEP"]["vwap_gate"]["distance_pct"] == -3.0
    assert decisions["DEEP"]["vwap_gate"]["gate_passed"] is False

    assert by_symbol["NEAR"]["candidate_status"] == "Strengthening"
    assert decisions["NEAR"]["vwap_gate"]["distance_pct"] == -0.5
    assert decisions["NEAR"]["vwap_gate"]["gate_passed"] is True

    assert by_symbol["ABOVE"]["candidate_status"] in {"Strengthening", "Entry Ready"}
    assert decisions["ABOVE"]["vwap_gate"]["distance_pct"] == 1.0
    assert decisions["ABOVE"]["vwap_gate"]["gate_passed"] is True

    for symbol, record in by_symbol.items():
        assert (
            record["vwap_distance_pct"]
            == decisions[symbol]["vwap_gate"]["distance_pct"]
        )


def test_scanner_v2_volume_gate_adapts_by_market_session():
    from datetime import datetime, timezone

    from mide.scanner_v2 import apply_scanner_v2

    record = {
        **base(
            symbol="ADAPT",
            volume=300_000,
            dollar_volume=160_000,
            rvol_proxy=1.0,
            volume_acceleration=1.3,
        ).__dict__,
        "timeframes": {"1m": {"above_vwap": True, "supertrend": True}},
        "reasons": [],
        "cautions": [],
    }

    premarket = apply_scanner_v2(
        [record], {}, scan_time=datetime(2026, 7, 23, 12, 0, tzinfo=timezone.utc)
    )[0]
    open_scan = apply_scanner_v2(
        [record], {}, scan_time=datetime(2026, 7, 23, 13, 45, tzinfo=timezone.utc)
    )[0]

    assert premarket["volume_session_diagnostics"] == {
        "current_session": "Pre-Market",
        "expected_minimum_volume": 225_000,
        "actual_volume": 300_000,
        "volume_passed": True,
        "expected_minimum_dollar_volume": 112_500,
        "actual_dollar_volume": 160_000,
        "dollar_volume_passed": True,
        "expected_minimum_rvol": 0.68,
        "actual_rvol": 1.0,
        "rvol_passed": True,
        "passed": True,
    }
    assert open_scan["volume_session_diagnostics"]["current_session"] == "Open"
    assert open_scan["volume_session_diagnostics"]["expected_minimum_volume"] == 800_000
    assert open_scan["volume_session_diagnostics"]["actual_volume"] == 300_000
    assert open_scan["volume_session_diagnostics"]["passed"] is False
    assert open_scan["strengthening_decision"]["volume_gate"]["passed"] is False


def test_scanner_v2_midday_and_power_hour_volume_expectations():
    from datetime import datetime, timezone

    from mide.scanner_v2 import apply_scanner_v2

    record = {
        **base(
            symbol="DAY", volume=500_000, dollar_volume=250_000, rvol_proxy=1.5
        ).__dict__,
        "timeframes": {"1m": {"above_vwap": True, "supertrend": True}},
        "reasons": [],
        "cautions": [],
    }

    midday = apply_scanner_v2(
        [record], {}, scan_time=datetime(2026, 7, 23, 16, 30, tzinfo=timezone.utc)
    )[0]
    power_hour = apply_scanner_v2(
        [record], {}, scan_time=datetime(2026, 7, 23, 19, 30, tzinfo=timezone.utc)
    )[0]

    assert midday["volume_session_diagnostics"]["current_session"] == "Midday"
    assert midday["volume_session_diagnostics"]["expected_minimum_volume"] == 375_000
    assert midday["volume_session_diagnostics"]["passed"] is True
    assert power_hour["volume_session_diagnostics"]["current_session"] == "Power Hour"
    assert (
        power_hour["volume_session_diagnostics"]["expected_minimum_volume"] == 625_000
    )
    assert power_hour["volume_session_diagnostics"]["passed"] is False


def test_sequential_trend_confirmation_rewards_ordered_expansion():
    from datetime import datetime, timezone

    from mide.scanner_v2 import apply_scanner_v2

    scan_time = datetime(2026, 7, 23, 13, 31, tzinfo=timezone.utc)
    record = {
        **base(timeframe_confirmations=4).__dict__,
        "opportunity_score": 70,
        "status": "MONITOR",
        "supertrend_30s_flip": True,
        "timeframes": {
            "1m": {"above_vwap": True, "supertrend": True},
            "3m": {"above_vwap": True, "supertrend": True},
            "5m": {"above_vwap": True, "supertrend": True},
        },
        "reasons": [],
        "cautions": [],
    }

    ranked = apply_scanner_v2([record], {}, scan_time=scan_time)
    sequence = ranked[0]["trend_confirmation_sequence"]

    assert sequence["condition"] == "Stable"
    assert sequence["progression_count"] == 4
    assert sequence["conflict_count"] == 0
    assert [step["state"] for step in sequence["ladder"]] == [
        "confirmed",
        "confirmed",
        "confirmed",
        "confirmed",
    ]
    assert [event["timeframe"] for event in ranked[0]["trend_confirmation_events"]] == [
        "30s",
        "1m",
        "3m",
        "5m",
    ]
    assert (
        ranked[0]["trend_confirmation_events"][0]["confirmed_at"]
        == "2026-07-23T13:31:00+00:00"
    )


def test_sequential_trend_confirmation_penalizes_broken_order():
    from datetime import datetime, timezone

    from mide.scanner_v2 import apply_scanner_v2

    scan_time = datetime(2026, 7, 23, 13, 31, tzinfo=timezone.utc)
    ordered = {
        **base(symbol="ORD", timeframe_confirmations=3).__dict__,
        "opportunity_score": 70,
        "status": "MONITOR",
        "supertrend_30s_flip": True,
        "timeframes": {
            "1m": {"above_vwap": True, "supertrend": True},
            "3m": {"above_vwap": True, "supertrend": True},
            "5m": {"above_vwap": False, "supertrend": False},
        },
        "reasons": [],
        "cautions": [],
    }
    broken = {
        **base(symbol="BRK", timeframe_confirmations=3).__dict__,
        "opportunity_score": 70,
        "status": "MONITOR",
        "supertrend_30s_flip": True,
        "timeframes": {
            "1m": {"above_vwap": False, "supertrend": False},
            "3m": {"above_vwap": True, "supertrend": True},
            "5m": {"above_vwap": True, "supertrend": True},
        },
        "reasons": [],
        "cautions": [],
    }

    ranked = {
        r["symbol"]: r
        for r in apply_scanner_v2([ordered, broken], {}, scan_time=scan_time)
    }

    assert ranked["ORD"]["trend_condition"] == "Stable"
    assert ranked["ORD"]["trend_confirmation_sequence"]["progression_count"] == 3
    assert ranked["BRK"]["trend_condition"] == "Weakening"
    assert ranked["BRK"]["trend_confirmation_sequence"]["progression_count"] == 1
    assert ranked["BRK"]["trend_confirmation_sequence"]["conflict_count"] == 2
    assert "conflicting SuperTrend timeframe order" in ranked["BRK"]["cautions"]
    assert ranked["ORD"]["scanner_v2_score"] > ranked["BRK"]["scanner_v2_score"]


def test_participation_surge_detects_quiet_to_institutional_transition_without_news():
    from datetime import datetime, timezone

    from mide.scanner_v2 import apply_scanner_v2

    prior = {
        "STAK": {
            "candidate_status": "New",
            "volume_acceleration": 1.05,
            "rvol_proxy": 1.1,
            "vwap_relation": "testing",
            "vwap_distance_pct": -0.2,
            "supertrend_bullish": False,
            "scanner_v2_score": 20,
        }
    }
    record = {
        **base(
            symbol="STAK",
            pct_change=1.8,
            headline="",
            catalyst_score=0,
            news_age_hours=None,
            supertrend_bullish=True,
            supertrend_flip=True,
            vwap_relation="above",
            vwap_distance_pct=0.15,
            volume_acceleration=2.4,
        ).__dict__,
        "volume_acceleration_1m": 4.6,
        "volume_acceleration_3m": 3.2,
        "volume_acceleration_5m": 2.5,
        "dollar_flow_acceleration_1m": 4.8,
        "dollar_flow_acceleration_3m": 3.4,
        "dollar_flow_acceleration_5m": 2.7,
        "current_dollar_flow_1m": 120_000,
        "current_dollar_flow_3m": 310_000,
        "current_dollar_flow_5m": 470_000,
        "baseline_dollar_flow_per_minute": 35_000,
        "expansion_quality": 82,
        "opportunity_score": 36,
        "participation_score": 44,
        "status": "PASS",
        "headline": "",
        "timeframes": {},
        "reasons": [],
        "cautions": [],
    }

    ranked = apply_scanner_v2(
        [record], prior, datetime(2026, 7, 24, 14, 0, tzinfo=timezone.utc)
    )
    surge = ranked[0]["participation_surge_diagnostics"]

    assert ranked[0]["participation_surge_detected"] is True
    assert ranked[0]["participation_surge_alert"] == "Participation Surge Detected"
    assert surge["participation_score"] >= 72
    assert surge["current_phase"] == ranked[0]["market_phase"]
    assert ranked[0]["alert_event"] is True
    assert "Participation Surge" in " ".join(ranked[0]["reasons"])


def test_participation_surge_does_not_reward_extended_established_trend():
    from mide.scanner_v2 import participation_surge_diagnostics

    record = {
        "price": 1.0,
        "calculated_vwap": 0.92,
        "vwap_distance_pct": 8.7,
        "supertrend_bullish": True,
        "supertrend_flip": False,
        "volume_acceleration_1m": 4.0,
        "volume_acceleration_3m": 3.0,
        "volume_acceleration_5m": 2.5,
        "dollar_flow_acceleration_1m": 4.0,
        "dollar_flow_acceleration_3m": 3.0,
        "dollar_flow_acceleration_5m": 2.5,
        "expansion_quality": 80,
    }
    prior = {"supertrend_bullish": True, "volume_acceleration": 2.0, "rvol_proxy": 3.0}

    surge = participation_surge_diagnostics(record, prior)

    assert surge["detected"] is False
    assert surge["st_status"] == "established bullish"
    assert surge["vwap_state"] == "extended above VWAP"


def test_momentum_quality_separates_orderly_expansion_from_chaotic_spike():
    from datetime import datetime, timezone

    from mide.scanner_v2 import apply_scanner_v2, momentum_quality_diagnostics

    scan_time = datetime(2026, 7, 24, 15, 0, tzinfo=timezone.utc)
    clean = {
        **base(symbol="CLEAN", pct_change=22, higher_lows=True, near_hod=True).__dict__,
        "timeframes": {
            "1m": {"above_vwap": True, "supertrend": True},
            "3m": {"above_vwap": True, "supertrend": True},
            "5m": {"above_vwap": True, "supertrend": True},
        },
        "vwap_distance_pct": 0.45,
        "volume_acceleration_1m": 2.6,
        "volume_acceleration_3m": 2.4,
        "volume_acceleration_5m": 2.2,
        "dollar_flow_acceleration_1m": 2.8,
        "dollar_flow_acceleration_3m": 2.5,
        "dollar_flow_acceleration_5m": 2.3,
        "expansion_quality": 90,
        "opportunity_score": 70,
        "status": "MONITOR",
        "reasons": [],
        "cautions": [],
    }
    chaotic = {
        **base(
            symbol="CHAOS",
            pct_change=22,
            higher_lows=False,
            near_hod=False,
            green_volume_ratio=0.8,
        ).__dict__,
        "timeframes": {
            "1m": {"above_vwap": True, "supertrend": False},
            "3m": {"above_vwap": False, "supertrend": True},
            "5m": {"above_vwap": True, "supertrend": False},
        },
        "vwap_distance_pct": 5.8,
        "volume_acceleration_1m": 5.8,
        "volume_acceleration_3m": 1.3,
        "volume_acceleration_5m": 1.1,
        "dollar_flow_acceleration_1m": 5.9,
        "dollar_flow_acceleration_3m": 1.2,
        "dollar_flow_acceleration_5m": 1.0,
        "expansion_quality": 24,
        "opportunity_score": 70,
        "status": "MONITOR",
        "reasons": [],
        "cautions": [],
    }

    clean_quality = momentum_quality_diagnostics(clean, {}, scan_time)
    chaotic_quality = momentum_quality_diagnostics(chaotic, {}, scan_time)
    ranked = apply_scanner_v2([chaotic, clean], {}, scan_time)

    assert clean_quality["score"] >= 75
    assert chaotic_quality["score"] < 45
    assert (
        clean_quality["factors"]["vwap_respect"]
        > chaotic_quality["factors"]["vwap_respect"]
    )
    assert (
        clean_quality["factors"]["st_integrity"]
        > chaotic_quality["factors"]["st_integrity"]
    )
    assert (
        clean_quality["factors"]["structure"] > chaotic_quality["factors"]["structure"]
    )
    assert (
        clean_quality["factors"]["participation"]
        > chaotic_quality["factors"]["participation"]
    )
    assert (
        clean_quality["factors"]["efficiency"]
        > chaotic_quality["factors"]["efficiency"]
    )
    assert ranked[0]["symbol"] == "CLEAN"
    assert ranked[0]["current_momentum"] > ranked[1]["current_momentum"]
    assert "momentum_quality_diagnostics" in ranked[0]


def test_trend_stability_separates_healthy_from_fragile_equal_momentum():
    from datetime import datetime, timezone
    from mide.scanner_v2 import apply_scanner_v2, trend_stability_diagnostics

    scan_time = datetime(2026, 7, 24, 14, 30, tzinfo=timezone.utc)
    healthy = {
        **base().__dict__,
        "symbol": "STABLE",
        "opportunity_score": 70,
        "scanner_v2_score": 70,
        "status": "MONITOR",
        "vwap_distance_pct": 0.4,
        "vwap_slope_pct": 0.35,
        "vwap_violation_count": 0,
        "vwap_cross_count": 0,
        "supertrend_flip_count": 1,
        "pullback_depth_pct": 0.6,
        "retracement_pct": 0.8,
        "fresh_higher_high": True,
        "follow_through_pct": 8,
        "new_high_rejection_count": 0,
        "expansion_quality": 88,
        "timeframes": {
            "1m": {"above_vwap": True, "supertrend": True},
            "3m": {"above_vwap": True, "supertrend": True},
            "5m": {"above_vwap": True, "supertrend": True},
        },
        "reasons": [],
        "cautions": [],
    }
    fragile = {
        **healthy,
        "symbol": "FRAGILE",
        "vwap_relation": "below",
        "vwap_distance_pct": -2.4,
        "vwap_slope_pct": -0.55,
        "vwap_violation_count": 3,
        "vwap_cross_count": 4,
        "supertrend_bullish": False,
        "supertrend_flip": False,
        "supertrend_flip_count": 5,
        "higher_lows": False,
        "lower_lows": True,
        "panic_candle": True,
        "pullback_depth_pct": 5.5,
        "retracement_pct": 6.0,
        "fresh_higher_high": False,
        "near_hod": False,
        "follow_through_pct": 0.5,
        "new_high_rejection_count": 3,
        "expansion_quality": 30,
        "timeframes": {
            "1m": {"above_vwap": False, "supertrend": False},
            "3m": {"above_vwap": True, "supertrend": False},
            "5m": {"above_vwap": False, "supertrend": True},
        },
    }

    healthy_stability = trend_stability_diagnostics(healthy, {}, scan_time)
    fragile_stability = trend_stability_diagnostics(fragile, {}, scan_time)
    ranked = apply_scanner_v2([fragile, healthy], {}, scan_time)

    assert healthy_stability["score"] >= 80
    assert fragile_stability["score"] < 45
    assert set(healthy_stability["factors"]) == {
        "vwap_stability",
        "st_stability",
        "pullback_quality",
        "continuation_strength",
    }
    assert ranked[0]["symbol"] == "STABLE"
    assert ranked[0]["trend_stability_score"] > ranked[1]["trend_stability_score"]
    assert ranked[0]["current_momentum"] > ranked[1]["current_momentum"]


def test_trigger_diagnostics_explain_failed_conditions():
    from datetime import datetime, timezone

    from mide.scanner_v2 import apply_scanner_v2

    record = {
        **base(
            symbol="STAK", price=1.097, vwap_relation="above", vwap_distance_pct=9.7
        ).__dict__,
        "calculated_vwap": 1.0,
        "supertrend_30s_flip": True,
        "supertrend_30s_flip_age_seconds": 14 * 60,
        "volume_acceleration_1m": 0.8,
        "volume_acceleration_3m": 0.7,
        "volume_acceleration_5m": 0.6,
        "dollar_flow_acceleration_1m": 0.8,
        "dollar_flow_acceleration_3m": 0.7,
        "dollar_flow_acceleration_5m": 0.6,
        "expansion_quality": 30,
        "opportunity_score": 50,
        "status": "MONITOR",
        "reasons": [],
        "cautions": [],
        "timeframes": {},
    }

    ranked = apply_scanner_v2(
        [record], {}, datetime(2026, 7, 24, 14, 0, tzinfo=timezone.utc)
    )
    diagnostics = ranked[0]["trigger_diagnostics"]

    assert ranked[0]["trigger"] == "NO"
    assert diagnostics["failed_conditions"] == [
        "participation",
        "supertrend_flip",
        "vwap",
        "not_extended",
        "expansion_beginning",
    ]
    assert "Price 9.7% above VWAP" in diagnostics["reasons"]
    assert "ST flip occurred 14 minutes ago" in diagnostics["reasons"]
    assert "Participation declining" in diagnostics["reasons"]


def test_trigger_diagnostics_yes_when_all_conditions_pass():
    from datetime import datetime, timezone

    from mide.scanner_v2 import apply_scanner_v2

    record = {
        **base(
            symbol="STAK", price=1.006, vwap_relation="above", vwap_distance_pct=0.6
        ).__dict__,
        "calculated_vwap": 1.0,
        "supertrend_30s_flip": True,
        "supertrend_30s_flip_age_seconds": 90,
        "volume_acceleration_1m": 4.6,
        "volume_acceleration_3m": 3.2,
        "volume_acceleration_5m": 2.5,
        "dollar_flow_acceleration_1m": 4.8,
        "dollar_flow_acceleration_3m": 3.4,
        "dollar_flow_acceleration_5m": 2.7,
        "expansion_quality": 82,
        "opportunity_score": 50,
        "status": "MONITOR",
        "reasons": [],
        "cautions": [],
        "timeframes": {},
    }

    ranked = apply_scanner_v2(
        [record], {}, datetime(2026, 7, 24, 14, 0, tzinfo=timezone.utc)
    )
    diagnostics = ranked[0]["trigger_diagnostics"]

    assert ranked[0]["trigger"] == "YES"
    assert diagnostics["failed_conditions"] == []
    assert "ST flipped 90 seconds ago" in diagnostics["reasons"]
    assert "0.6% above VWAP" in diagnostics["reasons"]
    assert "Not extended" in diagnostics["reasons"]
    assert "Expansion beginning" in diagnostics["reasons"]


def test_scanner_v2_hard_rejects_clean_structure_when_participation_fails():
    from datetime import datetime, timezone

    from mide.scanner_v2 import apply_scanner_v2

    record = {
        **base(
            symbol="SMRT",
            volume=120_000,
            dollar_volume=60_000,
            rvol_proxy=0.7,
            volume_acceleration=0.9,
            green_volume_ratio=0.95,
        ).__dict__,
        "calculated_vwap": 0.50,
        "volume_acceleration_1m": 0.9,
        "volume_acceleration_3m": 0.85,
        "dollar_flow_acceleration_1m": 0.8,
        "dollar_flow_acceleration_3m": 0.8,
        "dollar_flow_acceleration_5m": 0.8,
        "expansion_quality": 45,
        "opportunity_score": 80,
        "participation_score": 20,
        "status": "WATCH NOW",
        "timeframes": {},
        "reasons": [],
        "cautions": [],
    }

    ranked = apply_scanner_v2(
        [record], {}, datetime(2026, 7, 24, 14, 0, tzinfo=timezone.utc)
    )

    assert ranked[0]["candidate_status"] == "Rejected – No Participation"
    assert ranked[0]["qualified_for_ranking"] is False
    assert ranked[0]["scanner_v2_score"] == 0
    assert ranked[0]["participation_gate"]["status"] == "FAIL"
    assert ranked[0]["structure_gate"]["status"] == "PASS"
    assert ranked[0]["rejection_reason"] == "No Participation"
    assert (
        "Dollar flow not increasing"
        in ranked[0]["participation_gate"]["failed_reasons"]
    )


def test_participation_gate_rejection_is_separated_from_actionable_collection():
    from datetime import datetime, timezone

    from mide.scanner_v2 import apply_scanner_v2
    from mide.ui import actionable_candidate_records, rejected_candidate_records

    rejected_source = {
        **base(
            symbol="FAILPG",
            volume=1_000,
            dollar_volume=500,
            rvol_proxy=1.0,
            volume_acceleration=0.7,
            green_volume_ratio=0.7,
        ).__dict__,
        "volume_acceleration_1m": 0.7,
        "volume_acceleration_3m": 0.7,
        "dollar_flow_acceleration_1m": 0.7,
        "dollar_flow_acceleration_3m": 0.7,
        "dollar_flow_acceleration_5m": 0.7,
        "opportunity_score": 45,
        "status": "PASS",
        "timeframes": {},
        "reasons": [],
        "cautions": [],
    }

    scanner_output = apply_scanner_v2(
        [rejected_source], {}, datetime(2026, 7, 24, 14, 0, tzinfo=timezone.utc)
    )

    assert actionable_candidate_records(scanner_output) == []
    assert [
        record["symbol"] for record in rejected_candidate_records(scanner_output)
    ] == ["FAILPG"]
    rejected = rejected_candidate_records(scanner_output)[0]
    assert rejected["candidate_status"] == "Rejected – No Participation"
    assert rejected["participation_gate"]["failed_reasons"]
    assert rejected["participation_gate"]["failed_criteria"]
    assert {"condition", "measured", "threshold"} <= set(
        rejected["participation_gate"]["failed_criteria"][0]
    )


def test_participation_passing_record_remains_actionable_and_mixed_inputs_are_split():
    from datetime import datetime, timezone

    from mide.scanner_v2 import apply_scanner_v2
    from mide.ui import actionable_candidate_records, rejected_candidate_records

    valid = {
        **base(symbol="VALID").__dict__,
        "opportunity_score": 80,
        "status": "MONITOR",
        "timeframes": {"1m": {"above_vwap": True, "supertrend": True}},
        "reasons": [],
        "cautions": [],
    }
    rejected = {
        **base(
            symbol="REJECT",
            volume=1_000,
            dollar_volume=500,
            rvol_proxy=1.0,
            volume_acceleration=0.7,
            green_volume_ratio=0.7,
        ).__dict__,
        "volume_acceleration_1m": 0.7,
        "volume_acceleration_3m": 0.7,
        "dollar_flow_acceleration_1m": 0.7,
        "dollar_flow_acceleration_3m": 0.7,
        "dollar_flow_acceleration_5m": 0.7,
        "opportunity_score": 45,
        "status": "PASS",
        "timeframes": {},
        "reasons": [],
        "cautions": [],
    }

    scanner_output = apply_scanner_v2(
        [valid, rejected], {}, datetime(2026, 7, 24, 14, 0, tzinfo=timezone.utc)
    )

    assert [
        record["symbol"] for record in actionable_candidate_records(scanner_output)
    ] == ["VALID"]
    assert [
        record["symbol"] for record in rejected_candidate_records(scanner_output)
    ] == ["REJECT"]

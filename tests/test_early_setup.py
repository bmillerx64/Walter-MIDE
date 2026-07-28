from mide.early_setup import (
    early_setup_evaluation,
    enrich_early_setups,
    newly_entered_symbols,
    top_early_setups,
)
from mide.scanner_v2 import trigger_diagnostics
from mide.ui import early_setups_markup
from mide.ui import timing_status_markup


def record(**changes):
    base = dict(
        symbol="FIRE",
        price=1.18,
        pct_change=12,
        dollar_volume=800_000,
        volume_acceleration=2.2,
        rvol_proxy=2.5,
        vwap_relation="above",
        vwap_reclaimed_last_10m=True,
        supertrend_bullish=True,
        ema5_relation="above",
        ema65_relation="above",
        higher_lows=True,
        participation_surge_score=50,
        expansion_quality=40,
        supertrend_flip=False,
        vwap_distance_pct=4,
    )
    base.update(changes)
    return base


def test_volume_expansion_reclaim_and_bullish_supertrend_qualify():
    assert early_setup_evaluation(record())["qualified"] is True


def test_news_setup_qualifies_before_strict_participation_threshold():
    result = early_setup_evaluation(
        record(
            headline="Company wins contract",
            news_age_hours=2,
            participation_surge_score=50,
        )
    )
    assert result["qualified"] and result["score"] >= 60
    assert (
        trigger_diagnostics(record(headline="Company wins contract", news_age_hours=2))[
            "passed"
        ]
        is False
    )


def test_extended_setup_is_visible_but_not_entry_ready():
    candidate = record(vwap_distance_pct=7.0)
    assert early_setup_evaluation(candidate)["qualified"]
    assert not trigger_diagnostics(candidate)["passed"]


def test_no_news_exceptional_tape_override():
    candidate = record(
        headline="",
        volume_acceleration=3.2,
        pct_change=8,
        dollar_volume=250_000,
        higher_lows=False,
        ema5_relation="below",
        ema65_relation="below",
    )
    result = early_setup_evaluation(candidate)
    assert result["override"] and result["qualified"]


def test_weak_volume_vwap_cross_does_not_qualify():
    assert not early_setup_evaluation(
        record(
            volume_acceleration=1.1,
            rvol_proxy=1.2,
            volume_above_preceding_15m_pace=False,
        )
    )["qualified"]


def test_duplicate_early_setup_alerts_are_suppressed():
    records = enrich_early_setups([record()])
    entered, active = newly_entered_symbols(records, set())
    duplicate, active_again = newly_entered_symbols(records, active)
    assert entered == ["FIRE"]
    assert duplicate == [] and active_again == active


def test_early_layer_does_not_change_entry_ready_logic_or_ranking():
    source = record(symbol="A")
    before = trigger_diagnostics(source)
    enriched = enrich_early_setups([source])[0]
    assert trigger_diagnostics(enriched) == before
    assert (
        enriched["qualified_for_entry"] if "qualified_for_entry" in enriched else True
    )


def test_panel_is_limited_to_highest_five_and_compact():
    records = enrich_early_setups(
        [record(symbol=f"S{i}", volume_acceleration=2 + i / 10) for i in range(7)]
    )
    assert len(top_early_setups(records)) == 5
    markup = early_setups_markup(records)
    assert "⚡ EARLY SETUPS" in markup and markup.count("Early Setup ") == 5
    assert "Next:" in markup


def test_timing_signals_before_breakout_are_early_setup():
    result = early_setup_evaluation(
        record(
            price=10.4,
            first_abnormal_volume_price=10,
            first_abnormal_volume_time="2026-07-28T14:30:00Z",
            first_vwap_reclaim_time="2026-07-28T14:31:00Z",
            first_supertrend_flip_time="2026-07-28T14:32:00Z",
            scan_time="2026-07-28T14:33:00Z",
        )
    )
    assert result["qualified"] and result["timing_state"] == "EARLY SETUP"
    assert result["detection_delay_seconds"] == 180


def test_detection_after_twenty_five_percent_move_and_halt_is_late():
    result = early_setup_evaluation(
        record(
            price=12.5,
            first_abnormal_volume_price=10,
            first_abnormal_volume_time="2026-07-28T14:00:00Z",
            first_halt_time="2026-07-28T14:10:00Z",
            vwap_reclaimed_last_10m=False,
            supertrend_flipped_last_10m=False,
            scan_time="2026-07-28T14:30:00Z",
        )
    )
    assert result["base_qualified"] and not result["qualified"]
    assert result["timing_state"] == "LATE MOMENTUM"
    assert result["percent_move_since_first_detection"] == 25
    assert "Detected +25% after ignition" in timing_status_markup(
        {"symbol": "LGHL", "early_setup": result}
    )


def test_breakout_within_three_completed_bars_is_early():
    result = early_setup_evaluation(
        record(
            price=15,
            first_abnormal_volume_price=10,
            first_halt_time="2026-07-28T14:10:00Z",
            broke_previous_15m_high_with_volume=True,
            breakout_age_completed_bars=3,
        )
    )
    assert result["qualified"]
    assert "breakout within 3 completed bars" in result["timing_conditions"]


def test_late_building_pullback_cannot_receive_retroactive_early_alert():
    prior = {
        "timing_state": "LATE MOMENTUM",
        "first_abnormal_volume_price": 10,
        "first_abnormal_volume_time": "2026-07-28T14:00:00Z",
        "first_halt_time": "2026-07-28T14:10:00Z",
    }
    result = early_setup_evaluation(
        record(price=10.5, pullback=True, candidate_status="Strengthening"), prior
    )
    assert result["base_qualified"] and not result["qualified"]
    assert result["timing_state"] == "WAIT FOR RESET"
    assert result["alert_eligible"] is False


def test_alert_is_suppressed_past_twelve_percent_even_if_other_timing_rule_applies():
    result = early_setup_evaluation(
        record(
            price=11.3,
            first_abnormal_volume_price=10,
            broke_previous_15m_high_with_volume=True,
            breakout_age_completed_bars=1,
        )
    )
    assert result["qualified"] and result["alert_eligible"] is False

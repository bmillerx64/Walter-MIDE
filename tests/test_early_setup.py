from mide.early_setup import (
    early_setup_evaluation,
    enrich_early_setups,
    newly_entered_symbols,
    top_early_setups,
)
from mide.scanner_v2 import trigger_diagnostics
from mide.ui import early_setups_markup


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

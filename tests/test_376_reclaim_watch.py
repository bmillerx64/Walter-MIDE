from mide.gs310_unified_opportunity_state import DEVELOPING, LOOK_NOW
from mide.gs375_operator_awareness import AWARENESS_ONLY_KEY
from mide.gs376_reclaim_watch import (
    RECLAIM_WATCH,
    RECLAIM_WATCH_KEY,
    augment_reclaim_records,
    install,
    reclaim_opportunity_state,
    reclaim_watch_evaluation,
    reclaim_watch_eligible,
)


def _reclaim_record(**overrides):
    record = {
        "symbol": "DSS",
        "price": 0.82,
        "pct_change": 48.0,
        "dollar_volume": 8_000_000,
        "qualified_for_watch": False,
        "qualified_for_entry": False,
        "qualified_for_alert": False,
        "discovery_reasons": ["Webull native: day_gainers"],
        "vwap_relation": "below",
        "vwap_distance_pct": -3.0,
        "supertrend_bullish": True,
        "supertrend_flip": True,
        "supertrend_flip_age_seconds": 90.0,
        "participation_surge_score": 35.0,
        "expansion_quality": 45.0,
        "volume_acceleration": 0.9,
        "source_bar_age_seconds": 30.0,
        "opportunity_pulse_previous": {
            "symbol": "DSS",
            "pct_change": 70.0,
            "vwap_relation": "below",
            "vwap_distance_pct": -6.0,
            "supertrend_bullish": False,
            "volume_acceleration": 0.8,
        },
    }
    record.update(overrides)
    return record


def test_resetting_major_leader_gets_reclaim_watch_even_inside_narrow_gs373_exception():
    record = _reclaim_record()

    evaluation = reclaim_watch_evaluation(record)

    assert evaluation["eligible"] is True
    assert evaluation["current_top_mover"] is True
    assert evaluation["trend_recovery"] is True
    assert evaluation["vwap_reconstruction"] is True

    rows = augment_reclaim_records([record], [])
    assert len(rows) == 1
    assert rows[0][RECLAIM_WATCH_KEY] is True
    assert rows[0][AWARENESS_ONLY_KEY] is True
    assert rows[0]["qualified_for_entry"] is False
    assert rows[0]["qualified_for_alert"] is False

    view = reclaim_opportunity_state(rows[0])
    assert view["state"] == RECLAIM_WATCH
    assert "rebuilding after a reset" in view["reason"].lower()
    assert "entry remains locked" in view["next_step"].lower()


def test_fami_style_seven_percent_below_vwap_stays_suppressed():
    far_below = _reclaim_record(
        symbol="FAMI",
        vwap_distance_pct=-7.0,
        opportunity_pulse_previous={
            "vwap_relation": "below",
            "vwap_distance_pct": -10.0,
            "supertrend_bullish": False,
        },
    )

    assert reclaim_watch_eligible(far_below) is False
    assert augment_reclaim_records([far_below], []) == []


def test_reclaim_exception_never_ignores_source_bar_freshness():
    stale = _reclaim_record(source_bar_age_seconds=121.0)

    assert reclaim_watch_eligible(stale) is False
    assert augment_reclaim_records([stale], []) == []


def test_static_or_worsening_structure_is_not_called_reclaim():
    worsening = _reclaim_record(
        vwap_distance_pct=-3.0,
        opportunity_pulse_previous={
            "vwap_relation": "below",
            "vwap_distance_pct": -2.0,
            "supertrend_bullish": False,
        },
    )
    static_trend = _reclaim_record(
        supertrend_flip=False,
        supertrend_bullish=True,
        opportunity_pulse_previous={
            "vwap_relation": "below",
            "vwap_distance_pct": -5.0,
            "supertrend_bullish": True,
        },
    )

    assert reclaim_watch_eligible(worsening) is False
    assert reclaim_watch_eligible(static_trend) is False


def test_reclaim_requires_prior_continuity_and_explicit_fresh_bar():
    first_seen = _reclaim_record(opportunity_pulse_previous={})
    unknown_age = _reclaim_record(source_bar_age_seconds=None)

    assert reclaim_watch_eligible(first_seen) is False
    assert reclaim_watch_eligible(unknown_age) is False


def test_stronger_fresh_reignition_look_now_is_not_demoted_to_reclaim():
    record = _reclaim_record(
        vwap_relation="above",
        vwap_distance_pct=0.5,
        volume_acceleration=2.0,
        rvol_proxy=3.0,
        price_change_10m_pct=5.0,
        broke_previous_15m_high_with_volume=True,
        opportunity_pulse_previous={
            "vwap_relation": "below",
            "vwap_distance_pct": -1.5,
            "supertrend_bullish": False,
        },
    )
    assert "FRESH_REIGNITION" in reclaim_watch_evaluation(record)["attention_provenance"]

    view = reclaim_opportunity_state(
        record,
        state_function=lambda _record: {
            "state": LOOK_NOW,
            "color": "yellow",
            "reason": "fresh re-ignition",
            "next_step": "review",
        },
    )

    assert view["state"] == LOOK_NOW


def test_reclaim_priority_sits_between_look_now_and_developing():
    from mide import gs363_operator_attention_hierarchy as hierarchy
    from mide import gs310_unified_opportunity_state as unified

    install()

    assert hierarchy.STATE_PRIORITY[unified.LOOK_NOW] > hierarchy.STATE_PRIORITY[RECLAIM_WATCH]
    assert hierarchy.STATE_PRIORITY[RECLAIM_WATCH] > hierarchy.STATE_PRIORITY[unified.DEVELOPING]
    assert hierarchy.STATE_PRIORITY[unified.DEVELOPING] > hierarchy.STATE_PRIORITY[unified.CHASE_WAIT]


def test_non_reclaim_record_keeps_original_developing_state():
    ordinary = _reclaim_record(
        discovery_reasons=["Webull native: absolute_volume"],
    )
    view = reclaim_opportunity_state(
        ordinary,
        state_function=lambda _record: {
            "state": DEVELOPING,
            "color": "blue",
            "reason": "ordinary developing",
            "next_step": "monitor",
        },
    )

    assert view["state"] == DEVELOPING
    assert view["reason"] == "ordinary developing"

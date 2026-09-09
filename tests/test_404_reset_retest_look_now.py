from mide import gs310_unified_opportunity_state as unified
from mide.gs404_reset_retest_look_now import (
    RESET_RETEST_KEY,
    RESET_RETEST_PROVENANCE,
    augment_reset_retest_records,
    reset_retest_attention_evidence,
    reset_retest_opportunity_state,
)


def _ztg(**updates):
    record = {
        "symbol": "ZTG",
        "pct_change": 5.63,
        "vwap_relation": "below",
        "vwap_distance_pct": -0.8619,
        "source_bar_age_seconds": 45.0,
        "discovery_reasons": [
            "Webull OpenAPI universe",
            "Webull native: day_gainers",
            "Webull native: five_minute_movers",
        ],
        "timeframes": {
            "1m": {"above_vwap": False, "supertrend": True},
            "3m": {"above_vwap": False, "supertrend": True},
        },
        "participation_score": 31.1,
        "volume_acceleration": 3.3199,
        "dollar_flow_acceleration": 28.57,
        "qualified_for_watch": False,
        "qualified_for_entry": False,
        "qualified_for_alert": False,
        "opportunity_pulse_previous": {
            "symbol": "ZTG",
            "vwap_distance_pct": 7.985,
            "participation_score": 39.9,
            "volume_acceleration": 56.88,
            "candidate_status": "Entry Ready",
            "status": "PASS",
        },
    }
    record.update(updates)
    return record


def _base_state(state=unified.DEVELOPING):
    return {
        "state": state,
        "color": unified.STATE_COLORS[state],
        "reason": "base",
        "next_step": "base next",
    }


def test_ztg_live_specimen_becomes_reset_retest_attention():
    evidence = reset_retest_attention_evidence(_ztg())

    assert evidence["recent"] is True
    assert evidence["trigger"] == "RESET_RETEST_NEAR_VWAP"
    assert evidence["previous_extended"] is True
    assert evidence["near_vwap_now"] is True
    assert evidence["one_minute_supertrend_bullish"] is True
    assert evidence["participation_present"] is True
    assert evidence["flow_present"] is True
    assert evidence["current_webull_radar_attention"] is True
    assert evidence["fresh_source"] is True
    assert evidence["entry_authority_unchanged"] is True


def test_ztg_needs_no_news_to_get_chart_review_attention():
    record = _ztg()
    assert "headline" not in record
    assert "fresh_news" not in record
    assert reset_retest_attention_evidence(record)["recent"] is True


def test_eligible_nonactionable_row_is_injected_as_awareness_only_copy():
    visible = augment_reset_retest_records([_ztg()], [])

    assert len(visible) == 1
    row = visible[0]
    assert row["symbol"] == "ZTG"
    assert row[RESET_RETEST_KEY] is True
    assert row["operator_awareness_only"] is True
    assert row["qualified_for_watch"] is False
    assert row["qualified_for_entry"] is False
    assert row["qualified_for_alert"] is False


def test_existing_visible_row_is_tagged_without_duplication():
    source = _ztg()
    visible = augment_reset_retest_records([source], [source])

    assert len(visible) == 1
    assert visible[0][RESET_RETEST_KEY] is True


def test_reset_retest_promotes_developing_to_look_now_only():
    view = reset_retest_opportunity_state(
        _ztg(), lambda _: _base_state(unified.DEVELOPING)
    )

    assert view["state"] == unified.LOOK_NOW
    assert RESET_RETEST_PROVENANCE in view["attention_provenance"]
    assert view["reset_retest_attention"]["chart_review_only"] is True
    assert "investigation only" in view["next_step"].lower()


def test_stronger_watch_for_entry_state_is_never_downgraded():
    view = reset_retest_opportunity_state(
        _ztg(), lambda _: _base_state(unified.WATCH_FOR_ENTRY)
    )
    assert view["state"] == unified.WATCH_FOR_ENTRY


def test_prior_move_must_have_been_genuinely_extended():
    record = _ztg(opportunity_pulse_previous={"vwap_distance_pct": 4.99})
    assert reset_retest_attention_evidence(record)["recent"] is False


def test_current_price_must_have_reset_into_near_vwap_window():
    assert reset_retest_attention_evidence(_ztg(vwap_distance_pct=2.01))["recent"] is False
    assert reset_retest_attention_evidence(_ztg(vwap_distance_pct=-2.01))["recent"] is False


def test_bullish_one_minute_supertrend_is_required():
    record = _ztg(
        timeframes={
            "1m": {"above_vwap": False, "supertrend": False},
            "3m": {"above_vwap": False, "supertrend": True},
        }
    )
    assert reset_retest_attention_evidence(record)["recent"] is False


def test_current_webull_radar_provenance_is_required():
    record = _ztg(discovery_reasons=["Webull native: absolute_volume"])
    assert reset_retest_attention_evidence(record)["recent"] is False


def test_stale_source_bar_cannot_create_retest_attention():
    record = _ztg(source_bar_age_seconds=121.0)
    assert reset_retest_attention_evidence(record)["recent"] is False


def test_participation_and_real_flow_are_both_required():
    low_participation = _ztg(participation_score=19.9)
    assert reset_retest_attention_evidence(low_participation)["recent"] is False

    no_flow = _ztg(
        participation_score=80.0,
        volume_acceleration=0.99,
        dollar_flow_acceleration=1.24,
    )
    assert reset_retest_attention_evidence(no_flow)["recent"] is False

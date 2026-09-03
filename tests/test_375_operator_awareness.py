from mide.gs310_unified_opportunity_state import LOOK_NOW, WATCH_FOR_ENTRY, opportunity_state
from mide.gs375_operator_awareness import (
    AWARENESS_ONLY_KEY,
    augment_operator_records,
    awareness_safe_opportunity_state,
    operator_awareness_eligible,
)


def _record(**overrides):
    record = {
        "symbol": "LEAD",
        "price": 1.25,
        "pct_change": 35.0,
        "qualified_for_watch": False,
        "qualified_for_entry": False,
        "qualified_for_alert": False,
        "discovery_reasons": ["Webull native: day_gainers"],
        "vwap_relation": "above",
        "vwap_distance_pct": 0.5,
        "supertrend_bullish": False,
        "participation_surge_score": 30.0,
        "expansion_quality": 30.0,
        "source_bar_age_seconds": 30.0,
    }
    record.update(overrides)
    return record


def test_current_day_gainer_remains_visible_as_awareness_without_trade_authorization():
    leader = _record()

    rows = augment_operator_records([leader], [])

    assert len(rows) == 1
    assert rows[0]["symbol"] == "LEAD"
    assert rows[0][AWARENESS_ONLY_KEY] is True
    assert rows[0]["qualified_for_entry"] is False
    assert rows[0]["qualified_for_alert"] is False
    assert AWARENESS_ONLY_KEY not in leader
    assert awareness_safe_opportunity_state(rows[0])["state"] == LOOK_NOW


def test_awareness_only_record_can_never_become_watch_for_entry():
    leader = _record(
        supertrend_bullish=True,
        participation_surge_score=90.0,
        expansion_quality=80.0,
    )
    raw_view = opportunity_state(leader)
    assert raw_view["state"] == WATCH_FOR_ENTRY

    awareness = augment_operator_records([leader], [])[0]
    safe_view = awareness_safe_opportunity_state(awareness)

    assert safe_view["state"] == LOOK_NOW
    assert "not complete" in safe_view["reason"].lower()
    assert awareness["qualified_for_entry"] is False
    assert awareness["qualified_for_alert"] is False


def test_gs373_stale_and_far_below_vwap_rules_still_suppress_awareness():
    stale = _record(symbol="STALE", source_bar_age_seconds=121.0)
    far_below = _record(
        symbol="BELOW",
        vwap_relation="below",
        vwap_distance_pct=-2.1,
    )

    assert operator_awareness_eligible(stale) is False
    assert operator_awareness_eligible(far_below) is False
    assert augment_operator_records([stale, far_below], []) == []


def test_absolute_volume_only_discovery_does_not_create_operator_awareness_noise():
    volume_only = _record(
        symbol="VOL",
        discovery_reasons=["Webull native: absolute_volume"],
    )

    assert operator_awareness_eligible(volume_only) is False
    assert augment_operator_records([volume_only], []) == []


def test_existing_actionable_record_is_preserved_not_retagged():
    actionable = _record(symbol="READY", qualified_for_watch=True)

    rows = augment_operator_records([actionable], [actionable])

    assert rows == [actionable]
    assert AWARENESS_ONLY_KEY not in rows[0]

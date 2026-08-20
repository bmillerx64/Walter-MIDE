from copy import deepcopy

from mide.gs310_unified_opportunity_state import (
    CHASE_WAIT,
    DEVELOPING,
    HALTED,
    LOOK_NOW,
    WATCH_FOR_ENTRY,
    opportunity_state,
)


def _record(**overrides):
    record = {
        "symbol": "TEST",
        "vwap_relation": "above",
        "vwap_distance_pct": 0.8,
        "supertrend_bullish": True,
        "participation_surge_score": 80,
        "expansion_quality": 65,
        "volume_acceleration": 1.2,
        "discovery_reasons": ["Webull native: day_gainers"],
    }
    record.update(overrides)
    return record


def test_aligned_current_evidence_is_watch_for_entry_not_conflicting_entry_window():
    view = opportunity_state(_record())

    assert view["state"] == WATCH_FOR_ENTRY
    assert all(item["passed"] for item in view["evidence"])


def test_constructive_structure_with_light_participation_is_developing():
    view = opportunity_state(
        _record(participation_surge_score=45, expansion_quality=70, volume_acceleration=0.8)
    )

    assert view["state"] == DEVELOPING
    assert "developing" in view["reason"].lower()


def test_current_attention_without_confirmed_structure_is_look_now():
    view = opportunity_state(
        _record(
            vwap_relation="below",
            vwap_distance_pct=-1.0,
            supertrend_bullish=False,
            participation_surge_score=30,
            expansion_quality=30,
            volume_acceleration=0.7,
        )
    )

    assert view["state"] == LOOK_NOW
    assert view["attention_provenance"] == ["WEBULL_TOP_MOVER"]


def test_extended_symbol_is_chase_wait_even_if_other_evidence_is_strong():
    view = opportunity_state(_record(vwap_distance_pct=4.5))

    assert view["state"] == CHASE_WAIT
    assert "extended" in view["reason"].lower()


def test_halt_overrides_other_display_states():
    view = opportunity_state(_record(is_halted=True, vwap_distance_pct=8.0))

    assert view["state"] == HALTED
    assert "resumption" in view["next_step"].lower()


def test_display_derivation_does_not_mutate_scanner_record():
    record = _record()
    before = deepcopy(record)

    opportunity_state(record)

    assert record == before

from mide.escalation import MONITOR, TOO_EXTENDED, WATCH_CLOSELY, escalation_state
from mide.gs307_volume_regime_urgency import volume_regime_urgency


def _record(**overrides):
    value = {
        "symbol": "MGN",
        "candidate_status": "Watching",
        "qualified_for_entry": False,
        "vwap_relation": "above",
        "vwap_distance_pct": 1.2,
        "supertrend_bullish": True,
        "participation_score": 64,
        "rvol_proxy": 1.6,
        "volume_acceleration_1m": 2.4,
        "volume_acceleration_3m": 1.9,
        "opportunity_pulse_previous": {
            "candidate_status": "Watching",
            "vwap_relation": "above",
            "vwap_distance_pct": 0.9,
            "supertrend_bullish": True,
            "participation_score": 48,
            "rvol_proxy": 1.1,
            "volume_acceleration_1m": 1.1,
            "volume_acceleration_3m": 1.1,
        },
    }
    value.update(overrides)
    return value


def test_established_bullish_symbol_escalates_on_fresh_volume_regime_change():
    current = _record()
    result = volume_regime_urgency(current)
    assert result["promoted"] is True
    assert result["fresh_volume_regime"] is True
    assert result["vwap_supported"] is True
    assert result["trend_supported"] is True
    assert escalation_state(current) == WATCH_CLOSELY


def test_already_hot_tape_does_not_realert_without_a_new_regime_change():
    current = _record(
        volume_acceleration_1m=2.4,
        volume_acceleration_3m=1.9,
        opportunity_pulse_previous={
            "candidate_status": "Watching",
            "vwap_relation": "above",
            "supertrend_bullish": True,
            "participation_score": 62,
            "rvol_proxy": 1.6,
            "volume_acceleration_1m": 2.2,
            "volume_acceleration_3m": 1.8,
        },
    )
    assert volume_regime_urgency(current)["promoted"] is False
    assert escalation_state(current) == MONITOR


def test_regime_change_requires_fresh_continuity_and_supportive_structure():
    no_prior = _record(opportunity_pulse_previous={})
    assert volume_regime_urgency(no_prior)["promoted"] is False

    below_vwap = _record(vwap_relation="below", timeframes={})
    assert volume_regime_urgency(below_vwap)["promoted"] is False

    stale = _record(reevaluation_status="NOT_IN_CURRENT_REFRESH")
    assert volume_regime_urgency(stale)["promoted"] is False


def test_existing_too_extended_hard_stop_still_wins():
    current = _record(vwap_distance_pct=5.5)
    assert volume_regime_urgency(current)["promoted"] is True
    assert escalation_state(current) == TOO_EXTENDED


def test_volume_regime_observer_does_not_mutate_scanner_record():
    current = _record()
    before = repr(current)
    volume_regime_urgency(current)
    escalation_state(current)
    assert repr(current) == before

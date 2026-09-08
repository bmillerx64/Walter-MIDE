from mide import gs333_extreme_mover_operator_priority as extreme
from mide import gs390_st_vwap_validation_sequence as sequence
from mide import gs393_ignition_truth_extreme_decay as gs393
from mide import gs310_unified_opportunity_state as unified


def _ignition_record(**overrides):
    record = {
        "symbol": "GCDT",
        "price": 0.42,
        "pct_change": 28.0,
        "vwap_relation": "above",
        "vwap_distance_pct": 0.8,
        "vwap_reclaimed_last_10m": True,
        "vwap_reclaim_age_bars": 1,
        "supertrend_flip_age_seconds": 240.0,
        "volume_acceleration": 2.0,
        "participation_score": 24.0,
        "expansion_score": 44.0,
        "timeframes": {
            "1m": {"above_vwap": True, "supertrend": True},
            "3m": {"above_vwap": False, "supertrend": False},
        },
        "st_vwap_cross_events": {
            "1m": {"crossed": False, "recent": False, "new": False},
            "3m": {"crossed": False, "recent": False, "new": False},
        },
    }
    record.update(overrides)
    return record


def test_gs393_primary_ignition_does_not_require_literal_st_line_vwap_cross():
    evidence = gs393.ignition_evidence(_ignition_record())

    assert evidence["recent"] is True
    assert evidence["trigger"] == "VWAP_RECLAIM_WITH_BULLISH_1M_ST"
    assert evidence["three_minute_confirmation"] is False
    assert evidence["literal_st_line_vwap_cross_is_secondary"] is True


def test_gs393_fresh_1m_flip_above_vwap_is_also_primary_ignition():
    record = _ignition_record(
        vwap_reclaimed_last_10m=False,
        vwap_reclaim_age_bars=999,
        supertrend_flip_age_seconds=60.0,
    )
    evidence = gs393.ignition_evidence(record)

    assert evidence["recent"] is True
    assert evidence["trigger"] == "BULLISH_1M_ST_FLIP_ABOVE_VWAP"


def test_gs393_chase_guard_prevents_late_ignition_promotion():
    evidence = gs393.ignition_evidence(
        _ignition_record(vwap_distance_pct=4.2, supertrend_flip_age_seconds=30.0)
    )

    assert evidence["recent"] is False
    assert evidence["inside_chase_guard"] is False


def test_gs393_promotes_developing_to_look_now_but_never_overrides_chase():
    developing = {
        "state": unified.DEVELOPING,
        "color": unified.STATE_COLORS[unified.DEVELOPING],
        "reason": "still developing",
        "next_step": "wait",
        "attention_provenance": ["WEBULL_TOP_MOVER"],
        "evidence": [],
    }
    promoted = gs393._state_with_ignition(lambda _record: developing, _ignition_record())
    assert promoted["state"] == unified.LOOK_NOW
    assert "FRESH_1M_IGNITION" in promoted["attention_provenance"]

    chase = dict(developing)
    chase["state"] = unified.CHASE_WAIT
    chase["color"] = unified.STATE_COLORS[unified.CHASE_WAIT]
    unchanged = gs393._state_with_ignition(
        lambda _record: chase,
        _ignition_record(vwap_distance_pct=0.8),
    )
    assert unchanged["state"] == unified.CHASE_WAIT


def test_gs393_extended_extreme_banner_expires_but_reentry_is_fresh(monkeypatch):
    gs393.reset_state()
    original = extreme.extreme_market_event

    def fake_event(record):
        if not record.get("extreme", True):
            return None
        return {
            "symbol": record["symbol"],
            "pct_change": 120.0,
            "vwap_distance_pct": 20.0,
            "vwap_relation": "above",
            "trend": True,
            "halted": False,
            "headline": "catalyst",
            "provenance": ("WEBULL_TOP_MOVER",),
            "label": "EXTREME MOVER · DO NOT CHASE",
            "guidance": "wait",
        }

    monkeypatch.setattr(extreme, "extreme_market_event", fake_event)
    try:
        first_record, first_event = extreme.prioritized_extreme_event(
            [{"symbol": "GCDT", "extreme": True}], now=100.0
        )
        assert first_record["symbol"] == "GCDT"
        assert first_event["label"] == "EXTREME MOVER · DO NOT CHASE"

        expired_record, expired_event = extreme.prioritized_extreme_event(
            [{"symbol": "GCDT", "extreme": True}], now=281.0
        )
        assert expired_record is None
        assert expired_event is None

        # Leaving the extreme set clears the clock; a later re-entry is fresh.
        extreme.prioritized_extreme_event(
            [{"symbol": "GCDT", "extreme": False}], now=300.0
        )
        reentry_record, reentry_event = extreme.prioritized_extreme_event(
            [{"symbol": "GCDT", "extreme": True}], now=301.0
        )
        assert reentry_record["symbol"] == "GCDT"
        assert reentry_event is not None
    finally:
        monkeypatch.setattr(extreme, "extreme_market_event", original)
        gs393.reset_state()


def test_gs393_recorder_includes_primary_ignition_even_without_line_cross():
    payload = sequence.build_validation_sequence(
        {"scan_id": "scan-gcdt", "timestamp": "2026-09-08T14:20:00+00:00"},
        [_ignition_record()],
        provider=None,
    )

    assert payload["primary_ignition_definition"]
    assert payload["three_minute_role"] == "CONFIRMATION_NOT_PERMISSION"
    assert payload["symbol_count"] == 1
    row = payload["symbols"][0]
    assert row["symbol"] == "GCDT"
    assert row["operator_ignition"]["recent"] is True
    assert "3m confirmation pending" in row["sequence"]
    assert row["literal_st_line_vwap_cross_role"] == "SECONDARY_MATURATION_EVIDENCE"

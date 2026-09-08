from mide import gs310_unified_opportunity_state as unified
from mide import gs390_st_vwap_validation_sequence as sequence
from mide import gs394_consolidation_rearm as gs394


def _gcdt_rearm(**overrides):
    record = {
        "symbol": "GCDT",
        "price": 0.7159,
        "pct_change": 91.37,
        "vwap_relation": "above",
        "vwap_distance_pct": 7.9129,
        "vwap_reclaimed_last_10m": True,
        "supertrend_flip_age_seconds": 0.0,
        "price_change_10m_pct": 4.63,
        "participation_score": 47.4,
        "expansion_quality": 59.2,
        "volume_acceleration": 1.1526,
        "dollar_flow_acceleration_1m": 1.26,
        "last_five_candle_ranges_pct": [1.55, 2.94, 2.247, 3.067, 6.23],
        "timeframes": {
            "1m": {"above_vwap": True, "supertrend": True},
            "3m": {"above_vwap": True, "supertrend": True},
        },
    }
    record.update(overrides)
    return record


def test_gs394_gcdt_fixture_rearms_after_compression_breakout():
    evidence = gs394.consolidation_rearm_evidence(_gcdt_rearm())

    assert evidence["recent"] is True
    assert evidence["trigger"] == "CONSOLIDATION_REARM_1M"
    assert evidence["chart_review_only"] is True
    assert evidence["entry_chase_guard_still_authoritative"] is True
    assert evidence["three_minute_confirmation"] is True
    assert evidence["range_reset"] is True
    assert evidence["range_detail"]["range_expansion_multiple"] > 1.5


def test_gs394_rearm_stays_bounded_and_requires_3m_and_reset():
    assert gs394.consolidation_rearm_evidence(
        _gcdt_rearm(vwap_distance_pct=12.1)
    )["recent"] is False

    assert gs394.consolidation_rearm_evidence(
        _gcdt_rearm(timeframes={
            "1m": {"above_vwap": True, "supertrend": True},
            "3m": {"above_vwap": True, "supertrend": False},
        })
    )["recent"] is False

    assert gs394.consolidation_rearm_evidence(
        _gcdt_rearm(last_five_candle_ranges_pct=[5.0, 5.4, 5.1, 5.6, 6.0])
    )["recent"] is False


def test_gs394_rearm_requires_fresh_flip_and_nonvertical_10m_tape():
    assert gs394.consolidation_rearm_evidence(
        _gcdt_rearm(supertrend_flip_age_seconds=300.0)
    )["recent"] is False

    assert gs394.consolidation_rearm_evidence(
        _gcdt_rearm(price_change_10m_pct=9.0)
    )["recent"] is False


def test_gs394_chase_wait_can_become_look_now_for_chart_review_only():
    chase = {
        "state": unified.CHASE_WAIT,
        "color": unified.STATE_COLORS[unified.CHASE_WAIT],
        "reason": "extended",
        "next_step": "wait",
        "attention_provenance": ["WEBULL_TOP_MOVER"],
    }
    view = gs394._state_with_rearm(lambda _record: chase, _gcdt_rearm())

    assert view["state"] == unified.LOOK_NOW
    assert "CONSOLIDATION_REARM_1M" in view["attention_provenance"]
    assert view["consolidation_rearm"]["chart_review_only"] is True
    assert "not permission to chase" in view["next_step"].lower()


def test_gs394_never_overrides_watch_for_entry_or_halted():
    for state in (unified.WATCH_FOR_ENTRY, unified.HALTED):
        base = {
            "state": state,
            "color": unified.STATE_COLORS[state],
            "reason": "authoritative",
            "next_step": "keep",
        }
        view = gs394._state_with_rearm(lambda _record, base=base: base, _gcdt_rearm())
        assert view["state"] == state


def test_gs394_recorder_persists_rearm_observation(monkeypatch):
    original = sequence.build_validation_sequence

    def base_builder(scan, records, provider):
        return {"symbols": [{"symbol": "GCDT"}], "symbol_count": 1}

    monkeypatch.setattr(sequence, "build_validation_sequence", base_builder)
    try:
        gs394._install_recorder()
        payload = sequence.build_validation_sequence(
            {"scan_id": "gcdt-rearm"}, [_gcdt_rearm()], provider=None
        )
        assert payload["consolidation_rearm_count"] == 1
        assert payload["consolidation_rearm_role"] == "LOOK_NOW_CHART_REVIEW_ONLY"
        assert payload["consolidation_rearm_observations"][0]["symbol"] == "GCDT"
        assert payload["symbols"][0]["consolidation_rearm"]["recent"] is True
    finally:
        monkeypatch.setattr(sequence, "build_validation_sequence", original)

from pathlib import Path

from mide import gs310_unified_opportunity_state as unified
from mide import gs453_constructive_extension_developing as gs453


def _vsme(**overrides):
    record = {
        "symbol": "VSME",
        "vwap_relation": "above",
        "vwap_distance_pct": 2.4,
        "alignment_score": 2,
        "timeframe_alignment": {
            "30s": {"aligned": True},
            "1m": {"aligned": True},
            "3m": {"aligned": False},
        },
        "price_change_10m_pct": 2.8,
        "participation_score": 36.0,
        "expansion_score": 44.0,
        "volume_acceleration": 0.71,
        "dollar_flow_acceleration": 0.84,
        "supertrend_bullish": True,
    }
    record.update(overrides)
    return record


def _chase_view():
    return {
        "state": unified.CHASE_WAIT,
        "color": unified.STATE_COLORS[unified.CHASE_WAIT],
        "reason": "Price is 2.4% above VWAP; the move is extended.",
        "next_step": "Wait for a reset.",
        "attention_provenance": ["WEBULL_TOP_MOVER"],
    }


def test_vwsm_live_geometry_becomes_developing_wait_for_volume():
    view = gs453._state_with_constructive_extension(
        lambda _record: _chase_view(), _vsme()
    )

    assert view["state"] == unified.DEVELOPING
    assert "momentum has not re-armed" in view["reason"]
    assert "fresh participation/volume" in view["next_step"]
    assert "3m confirmation" in view["next_step"]
    assert "do not chase" in view["next_step"].lower()
    evidence = view["constructive_extension"]
    assert evidence["display_only"] is True
    assert evidence["entry_chase_guard_still_authoritative"] is True
    assert evidence["thirty_second_aligned"] is True
    assert evidence["one_minute_aligned"] is True
    assert evidence["three_minute_aligned"] is False


def test_constructive_extension_is_bounded_and_does_not_hide_real_chase():
    for record in (
        _vsme(vwap_distance_pct=5.01),
        _vsme(vwap_distance_pct=9.0),
        _vsme(price_change_10m_pct=6.01),
        _vsme(alignment_score=1),
        _vsme(timeframe_alignment={
            "30s": {"aligned": False},
            "1m": {"aligned": True},
            "3m": {"aligned": True},
        }),
    ):
        view = gs453._state_with_constructive_extension(
            lambda _record: _chase_view(), record
        )
        assert view["state"] == unified.CHASE_WAIT


def test_constructive_extension_requires_both_30s_and_1m_alignment():
    for missing in ("30s", "1m"):
        alignment = {
            "30s": {"aligned": True},
            "1m": {"aligned": True},
            "3m": {"aligned": True},
        }
        alignment[missing] = {"aligned": False}
        record = _vsme(alignment_score=2, timeframe_alignment=alignment)
        assert gs453.constructive_extension_evidence(record)["qualifies"] is False


def test_fresh_flow_without_3m_confirmation_remains_developing_not_look_now():
    record = _vsme(
        participation_score=48.0,
        volume_acceleration=1.4,
        dollar_flow_acceleration=1.5,
    )
    view = gs453._state_with_constructive_extension(
        lambda _record: _chase_view(), record
    )

    assert view["state"] == unified.DEVELOPING
    assert "3m confirmation" in view["reason"]
    assert "not entry permission" in view["next_step"].lower()


def test_gs453_never_downgrades_existing_look_now_watch_or_halt():
    for state in (unified.LOOK_NOW, unified.WATCH_FOR_ENTRY, unified.HALTED):
        base = {
            "state": state,
            "color": unified.STATE_COLORS[state],
            "reason": "authoritative",
            "next_step": "keep",
        }
        view = gs453._state_with_constructive_extension(
            lambda _record, base=base: base, _vsme()
        )
        assert view == base


def test_true_three_of_three_bounded_structure_can_still_be_developing():
    record = _vsme(
        alignment_score=3,
        timeframe_alignment={
            "30s": {"aligned": True},
            "1m": {"aligned": True},
            "3m": {"aligned": True},
        },
        participation_score=35.0,
        volume_acceleration=0.5,
    )
    view = gs453._state_with_constructive_extension(
        lambda _record: _chase_view(), record
    )
    assert view["state"] == unified.DEVELOPING
    assert view["constructive_extension"]["three_minute_aligned"] is True


def test_gs453_is_display_only_and_installed_after_reset_retest():
    source = Path("mide/gs453_constructive_extension_developing.py").read_text(
        encoding="utf-8"
    )
    chain = Path("mide/gs392_operator_order_audio.py").read_text(encoding="utf-8")

    forbidden = (
        "qualified_for_entry =",
        "qualified_for_alert =",
        "participation_score =",
        "expansion_score =",
        "alignment_score =",
        "request_scan(",
        "place_order(",
    )
    assert not any(token in source for token in forbidden)
    assert "entry_chase_guard_still_authoritative" in source
    assert chain.index("install_gs404()") < chain.index("install_gs453()")
    assert chain.index("install_gs453()") < chain.index("install_gs406()")

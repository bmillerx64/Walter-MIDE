from pathlib import Path

from mide import gs310_unified_opportunity_state as unified
from mide import gs477_leader_reset_reignition as gs477


def _record(
    *,
    symbol="SDST",
    price=0.27,
    pct_change=69.0,
    vwap_distance_pct=0.0,
    participation_score=70.1,
    volume_acceleration=2.23,
    dollar_flow_acceleration=1.07,
    one_above=False,
    three_bullish=False,
    three_above=False,
    source_bar_timestamp="2026-09-17T14:38:00+00:00",
):
    return {
        "symbol": symbol,
        "price": price,
        "pct_change": pct_change,
        "vwap_distance_pct": vwap_distance_pct,
        "participation_score": participation_score,
        "volume_acceleration": volume_acceleration,
        "dollar_flow_acceleration": dollar_flow_acceleration,
        "source_bar_age_seconds": 15.0,
        "source_bar_timestamp": source_bar_timestamp,
        "discovery_reasons": ["Webull native: day_gainers"],
        "qualified_for_watch": False,
        "qualified_for_entry": False,
        "qualified_for_alert": False,
        "timeframes": {
            "30s": {
                "data_available": True,
                "supertrend_bullish": True,
                "above_vwap": True,
            },
            "1m": {
                "data_available": True,
                "current_supertrend_bullish": True,
                "current_above_vwap": one_above,
            },
            "3m": {
                "data_available": True,
                "current_supertrend_bullish": three_bullish,
                "current_above_vwap": three_above,
            },
        },
    }


def _base_state(_record):
    return {
        "state": unified.DEVELOPING,
        "color": unified.STATE_COLORS[unified.DEVELOPING],
        "reason": "ordinary developing",
        "next_step": "monitor",
        "attention_provenance": [],
    }


def setup_function():
    gs477.reset_leader_memory()


def test_exact_sdst_sequence_surfaces_reset_watch_then_reignition():
    # Earlier first push: Walter already knew SDST was a current leader and >5% above VWAP.
    extended = _record(
        price=0.2858,
        vwap_distance_pct=10.6,
        participation_score=62.3,
        source_bar_timestamp="2026-09-17T13:51:00+00:00",
    )
    marked = gs477.apply_leader_reset_marks([extended], now=0.0)
    assert "leader_reset_reignition" not in marked[0]

    # 10:38 ET: back near VWAP, 30s + 1m bullish, Participation 70.1, volume acceleration 2.23.
    reset = _record(
        price=0.2699,
        vwap_distance_pct=-1.4229,
        participation_score=70.1,
        volume_acceleration=2.23,
        dollar_flow_acceleration=1.07,
        one_above=False,
        source_bar_timestamp="2026-09-17T14:38:00+00:00",
    )
    reset_row = gs477.apply_leader_reset_marks([reset], now=47 * 60.0)[0]
    reset_evidence = reset_row["leader_reset_reignition"]
    assert reset_evidence["stage"] == gs477.RESET_WATCH
    assert reset_evidence["stage_fresh"] is True
    assert reset_evidence["one_minute_bullish"] is True
    assert reset_evidence["one_minute_above_vwap"] is False
    assert reset_evidence["participation_score"] == 70.1
    reset_state = gs477.leader_reset_opportunity_state(_base_state, reset_row)
    assert reset_state["state"] == unified.DEVELOPING
    assert "LEADER RESET WATCH" in reset_state["reason"]
    assert "Wait for primary VWAP reclaim" in reset_state["next_step"]

    # 10:40 ET: primary VWAP reclaimed while fast ST + flow stay constructive.
    reignition = _record(
        price=0.2799,
        vwap_distance_pct=1.4153,
        participation_score=64.6,
        volume_acceleration=1.98,
        dollar_flow_acceleration=2.17,
        one_above=True,
        source_bar_timestamp="2026-09-17T14:40:00+00:00",
    )
    reignition_row = gs477.apply_leader_reset_marks([reignition], now=49 * 60.0)[0]
    evidence = reignition_row["leader_reset_reignition"]
    assert evidence["stage"] == gs477.REIGNITION
    assert evidence["stage_fresh"] is True
    state = gs477.leader_reset_opportunity_state(_base_state, reignition_row)
    assert state["state"] == unified.LOOK_NOW
    assert "LEADER RE-IGNITION" in state["reason"]
    assert "3m is not yet confirmed" in state["reason"]
    assert reignition_row["qualified_for_entry"] is False
    assert reignition_row["qualified_for_alert"] is False


def test_three_minute_join_strengthens_explanation_without_entry_authority():
    gs477.apply_leader_reset_marks(
        [_record(vwap_distance_pct=9.0, source_bar_timestamp="2026-09-17T13:50:00+00:00")],
        now=0.0,
    )
    row = gs477.apply_leader_reset_marks(
        [
            _record(
                vwap_distance_pct=1.0,
                one_above=True,
                three_bullish=True,
                three_above=True,
                dollar_flow_acceleration=2.0,
                source_bar_timestamp="2026-09-17T14:40:00+00:00",
            )
        ],
        now=50 * 60.0,
    )[0]
    evidence = row["leader_reset_reignition"]
    assert evidence["stage"] == gs477.THREE_MINUTE_CONFIRMATION
    state = gs477.leader_reset_opportunity_state(_base_state, row)
    assert state["state"] == unified.LOOK_NOW
    assert "3m SuperTrend are now bullish" in state["reason"]
    assert row["qualified_for_entry"] is False
    assert row["qualified_for_alert"] is False


def test_msgy_like_near_vwap_reset_surfaces_on_confirmed_3m_structure_before_flow():
    # Sept. 25 MSGY live shape: previously extended leader resets into the
    # near-VWAP window with 30s/1m/3m bullish, but tape flow is still quiet.
    gs477.apply_leader_reset_marks(
        [
            _record(
                symbol="MSGY",
                price=3.26,
                pct_change=65.5,
                vwap_distance_pct=13.446,
                participation_score=72.3,
                source_bar_timestamp="2026-09-25T14:27:00+00:00",
            )
        ],
        now=0.0,
    )

    reset = _record(
        symbol="MSGY",
        price=2.865,
        pct_change=45.4,
        vwap_distance_pct=1.9186,
        participation_score=31.2,
        volume_acceleration=0.57,
        dollar_flow_acceleration=0.56,
        one_above=True,
        three_bullish=True,
        three_above=True,
        source_bar_timestamp="2026-09-25T14:35:00+00:00",
    )
    row = gs477.apply_leader_reset_marks([reset], now=8 * 60.0)[0]

    evidence = row["leader_reset_reignition"]
    assert evidence["stage"] == gs477.RESET_WATCH
    assert evidence["supporting_flow"] is False
    assert evidence["three_minute_structure_support"] is True
    assert evidence["reset_support_source"] == "3M_STRUCTURE"
    assert evidence["flow_required_for_reignition"] is True
    assert row["qualified_for_entry"] is False
    assert row["qualified_for_alert"] is False

    state = gs477.leader_reset_opportunity_state(_base_state, row)
    assert state["state"] == unified.DEVELOPING
    assert "LEADER RESET WATCH" in state["reason"]
    assert "3m SuperTrend structure is still confirmed" in state["reason"]
    assert "participation/flow has not re-accelerated yet" in state["reason"]
    assert "wait for renewed participation/flow before LOOK NOW" in state["next_step"]

    phrase = gs477.leader_reset_audio_phrase([row])
    assert "RESET WATCH" in phrase
    assert "30 second, 1 minute, and 3 minute SuperTrend bullish" in phrase
    assert "Flow has not re-accelerated yet" in phrase
    assert "Attention only" in phrase


def test_below_vwap_reset_can_never_be_promoted_to_look_now():
    gs477.apply_leader_reset_marks([_record(vwap_distance_pct=8.0)], now=0.0)
    row = gs477.apply_leader_reset_marks(
        [_record(vwap_distance_pct=-1.0, one_above=False, source_bar_timestamp="later")],
        now=10 * 60.0,
    )[0]
    assert row["leader_reset_reignition"]["stage"] == gs477.RESET_WATCH
    state = gs477.leader_reset_opportunity_state(_base_state, row)
    assert state["state"] == unified.DEVELOPING


def test_unproven_or_expired_leader_does_not_receive_reset_attention():
    ordinary = _record(vwap_distance_pct=-1.0)
    assert "leader_reset_reignition" not in gs477.apply_leader_reset_marks([ordinary], now=0.0)[0]

    gs477.apply_leader_reset_marks([_record(vwap_distance_pct=8.0)], now=0.0)
    expired = gs477.apply_leader_reset_marks(
        [_record(vwap_distance_pct=0.5, one_above=True, source_bar_timestamp="expired")],
        now=gs477.LEADER_MEMORY_TTL_SECONDS + 1.0,
    )[0]
    assert "leader_reset_reignition" not in expired


def test_stale_source_or_weak_flow_does_not_trigger_reset_watch():
    gs477.apply_leader_reset_marks([_record(vwap_distance_pct=8.0)], now=0.0)

    stale = _record(vwap_distance_pct=-1.0)
    stale["source_bar_age_seconds"] = 9999
    assert "leader_reset_reignition" not in gs477.apply_leader_reset_marks([stale], now=300.0)[0]

    weak = _record(
        vwap_distance_pct=-1.0,
        participation_score=70.0,
        volume_acceleration=0.4,
        dollar_flow_acceleration=0.6,
        source_bar_timestamp="weak",
    )
    assert "leader_reset_reignition" not in gs477.apply_leader_reset_marks([weak], now=360.0)[0]


def test_reset_and_reignition_audio_are_explicitly_attention_only():
    gs477.apply_leader_reset_marks([_record(vwap_distance_pct=8.0)], now=0.0)
    reset = gs477.apply_leader_reset_marks(
        [_record(vwap_distance_pct=-1.2, source_bar_timestamp="reset")], now=60.0
    )[0]
    phrase = gs477.leader_reset_audio_phrase([reset])
    assert "RESET WATCH" in phrase
    assert "Attention only" in phrase

    reignition = gs477.apply_leader_reset_marks(
        [_record(vwap_distance_pct=1.2, one_above=True, source_bar_timestamp="reignite")],
        now=120.0,
    )[0]
    phrase = gs477.leader_reset_audio_phrase([reignition])
    assert "LOOK NOW" in phrase
    assert "3 minute confirmation pending" in phrase


def test_active_nonactionable_row_is_injected_as_awareness_only_copy():
    gs477.apply_leader_reset_marks([_record(vwap_distance_pct=8.0)], now=0.0)
    row = gs477.apply_leader_reset_marks(
        [_record(vwap_distance_pct=-1.0, source_bar_timestamp="reset")], now=60.0
    )[0]
    visible = gs477.augment_leader_reset_records([row], [])
    assert len(visible) == 1
    assert visible[0]["operator_awareness_only"] is True
    assert visible[0]["qualified_for_entry"] is False
    assert visible[0]["qualified_for_alert"] is False


def test_gs477_is_installed_after_gs474_at_final_boundary():
    source = Path("mide/gs414_final_enriched_opportunity_order.py").read_text(encoding="utf-8")
    assert "gs477_leader_reset_reignition" in source
    install_body = source.split("def install() -> None:", 1)[1]
    assert install_body.index("_install_gs474()") < install_body.index("_install_gs477()")


def test_gs477_scope_lock_is_presentation_audio_only():
    source = Path("mide/gs477_leader_reset_reignition.py").read_text(encoding="utf-8")
    forbidden = (
        "qualified_for_entry =",
        "qualified_for_alert =",
        "qualified_for_watch =",
        "execute_order",
        "place_order",
        "get_bars(",
        "get_history(",
        "fetch_bars(",
        "WebullSDKClient",
    )
    for token in forbidden:
        assert token not in source

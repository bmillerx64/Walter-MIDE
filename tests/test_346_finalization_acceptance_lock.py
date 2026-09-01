from mide.gs310_unified_opportunity_state import DEVELOPING, opportunity_state
from mide.gs345_persistent_leader_escalation import LeaderSnapshot, persistent_leader_signal
from mide.webull_native_radar import DISCOVERY_FEED_KEYS, DISCOVERY_CONTRACT


def _leader_snap(gain, participation, expansion, volume, rank, *, halted=False, seen=1.0):
    return LeaderSnapshot(
        gain_pct=gain,
        participation=participation,
        expansion=expansion,
        volume=volume,
        vwap_distance_pct=0.8,
        above_vwap=True,
        supertrend_bullish=True,
        native_rank=rank,
        halted=halted,
        seen_at=seen,
    )


def test_finalization_lock_discovery_stays_four_native_attention_feeds():
    assert DISCOVERY_FEED_KEYS == (
        "day_gainers",
        "five_minute_movers",
        "absolute_volume",
        "relative_volume",
    )
    assert "FIVE_MINUTE_MOVERS" in DISCOVERY_CONTRACT


def test_finalization_lock_cpop_style_below_vwap_attention_never_becomes_look_now():
    view = opportunity_state({
        "symbol": "CPOP",
        "vwap_relation": "below",
        "vwap_distance_pct": -10.5,
        "supertrend_bullish": True,
        "participation_surge_score": 90,
        "expansion_quality": 80,
        "volume_acceleration": 2.0,
        "attention_provenance": ["WEBULL_TOP_MOVER"],
    })
    assert view["state"] == DEVELOPING
    assert "reclaims vwap" in view["next_step"].lower()


def test_finalization_lock_rdac_style_persistent_runner_is_leader():
    history = [
        _leader_snap(24, 38, 46, 1_200_000, 8, seen=1.0),
        _leader_snap(36, 43, 51, 2_000_000, 6, halted=True, seen=61.0),
    ]
    current = {
        "symbol": "RDAC",
        "change_ratio": 52.0,
        "participation_surge_score": 52,
        "expansion_quality": 60,
        "volume": 3_400_000,
        "vwap_distance_pct": 1.4,
        "supertrend_bullish": True,
        "ranks": {"five_minute_movers": 3, "day_gainers": 5},
        "halted": False,
    }
    ok, reason = persistent_leader_signal(current, history)
    assert ok is True
    assert "persistent top-10 leadership" in reason
    assert "resumed constructively after a halt" in reason


def test_finalization_lock_current_halt_is_never_promoted():
    history = [
        _leader_snap(24, 40, 48, 1_000_000, 8, seen=1.0),
        _leader_snap(34, 46, 54, 1_800_000, 5, seen=61.0),
    ]
    current = {
        "symbol": "HALT",
        "change_ratio": 55.0,
        "participation_surge_score": 55,
        "expansion_quality": 62,
        "volume": 3_000_000,
        "vwap_distance_pct": 1.0,
        "supertrend_bullish": True,
        "ranks": {"five_minute_movers": 2},
        "halted": True,
    }
    assert persistent_leader_signal(current, history) == (False, "currently halted")

from mide.gs345_persistent_leader_escalation import (
    LeaderSnapshot,
    apply_leader_marks,
    leader_recommendation,
    persistent_leader_signal,
    reset_leader_memory,
)


def _snap(gain, participation, expansion, volume, rank, *, above=True, bullish=True, halted=False, seen=1.0):
    return LeaderSnapshot(
        gain_pct=gain,
        participation=participation,
        expansion=expansion,
        volume=volume,
        vwap_distance_pct=1.0 if above else -1.0,
        above_vwap=above,
        supertrend_bullish=bullish,
        native_rank=rank,
        halted=halted,
        seen_at=seen,
    )


def _record(**overrides):
    row = {
        "symbol": "RDAC",
        "change_ratio": 56.6,
        "vwap_distance_pct": 1.4,
        "supertrend_bullish": True,
        "participation_surge_score": 74,
        "expansion_quality": 78,
        "volume": 7_300_000,
        "sources": ["day_gainers", "five_minute_movers"],
        "ranks": {"day_gainers": 4, "five_minute_movers": 2},
    }
    row.update(overrides)
    return row


def test_rdac_control_elevates_persistent_leader_before_late_confirmation():
    history = [
        _snap(24.0, 44, 50, 1_800_000, 9, seen=1.0),
        _snap(41.0, 58, 63, 3_100_000, 5, seen=61.0),
    ]

    ok, reason = persistent_leader_signal(_record(), history)

    assert ok is True
    assert "persistent top-10 leadership" in reason
    cue = leader_recommendation(_record(), history)
    assert cue["label"] == "LEADER · STAY ON IT"
    assert "not an entry call" in cue["guidance"].lower()


def test_prior_halt_can_strengthen_reason_but_current_halt_never_promotes():
    history = [
        _snap(24.0, 44, 50, 1_800_000, 9, halted=True),
        _snap(41.0, 58, 63, 3_100_000, 5, seen=61.0),
    ]
    ok, reason = persistent_leader_signal(_record(), history)
    assert ok is True
    assert "after a halt" in reason

    assert persistent_leader_signal(_record(halted=True), history) == (False, "currently halted")


def test_below_vwap_extended_or_bearish_names_do_not_promote():
    history = [_snap(24, 44, 50, 1_800_000, 9), _snap(41, 58, 63, 3_100_000, 5, seen=61)]
    assert persistent_leader_signal(_record(vwap_distance_pct=-0.1), history) == (False, "below VWAP")
    assert persistent_leader_signal(_record(vwap_distance_pct=3.5), history) == (False, "too extended")
    assert persistent_leader_signal(_record(supertrend_bullish=False), history) == (False, "SuperTrend not bullish")


def test_single_spike_without_persistent_native_rank_is_rejected():
    history = [
        _snap(8, 22, 30, 500_000, None),
        _snap(17, 34, 42, 1_100_000, 15, seen=61),
    ]
    ok, reason = persistent_leader_signal(_record(), history)
    assert ok is False
    assert reason == "native leadership not persistent"


def test_leader_must_strengthen_not_merely_remain_visible():
    history = [
        _snap(48, 68, 72, 6_800_000, 3),
        _snap(50, 69, 73, 6_900_000, 3, seen=61),
    ]
    ok, reason = persistent_leader_signal(
        _record(change_ratio=51, participation_surge_score=70, expansion_quality=74, volume=7_000_000, ranks={"day_gainers": 4}),
        history,
    )
    assert ok is False
    assert reason == "leadership not strengthening"


def test_apply_marks_requires_three_scan_persistence():
    reset_leader_memory()
    first = _record(change_ratio=24, participation_surge_score=44, expansion_quality=50, volume=1_800_000, ranks={"day_gainers": 9})
    second = _record(change_ratio=41, participation_surge_score=58, expansion_quality=63, volume=3_100_000, ranks={"day_gainers": 5})
    third = _record()

    assert "_gs345_leader" not in apply_leader_marks([first], now=1.0)[0]
    assert "_gs345_leader" not in apply_leader_marks([second], now=61.0)[0]
    marked = apply_leader_marks([third], now=121.0)[0]
    assert marked["_gs345_leader"]["label"] == "LEADER · STAY ON IT"

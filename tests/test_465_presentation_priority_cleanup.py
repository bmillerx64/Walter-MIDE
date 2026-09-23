from pathlib import Path

from mide import gs310_unified_opportunity_state as unified
from mide import gs333_extreme_mover_operator_priority as gs333
from mide import gs457_maturation_leader_priority as gs457
from mide import gs459_price_trajectory_attention as gs459
from mide import gs462_preflip_ignition_watch as gs462
from mide import gs465_presentation_priority_cleanup as gs465


def _patch_state_and_attention(
    monkeypatch,
    states,
    *,
    jet=(),
    early=(),
    fresh=(),
    trajectory=(),
    sustained=(),
):
    monkeypatch.setattr(
        unified,
        "opportunity_state",
        lambda record: {"state": states[record["symbol"]], "reason": "test"},
    )
    monkeypatch.setattr(
        gs462,
        "preflip_ignition_watch",
        lambda record: {
            "active": record["symbol"] in jet or record["symbol"] in early,
            "jet_fuel": record["symbol"] in jet,
            "one_minute": {"st_gap_pct": 0.4},
            "three_minute": {"st_gap_pct": 0.8},
        },
    )
    monkeypatch.setattr(
        gs457,
        "maturation_attention",
        lambda record: {
            "fresh_maturation": record["symbol"] in fresh,
            "sustained_confirmation": record["symbol"] in sustained,
        },
    )
    monkeypatch.setattr(
        gs459,
        "trajectory_attention",
        lambda record: {"active": record["symbol"] in trajectory},
    )


def test_card_stack_is_strictly_state_contiguous_even_with_attention_lifts(monkeypatch):
    states = {
        "WATCH": unified.WATCH_FOR_ENTRY,
        "LOOK": unified.LOOK_NOW,
        "DEV1": unified.DEVELOPING,
        "DEV2": unified.DEVELOPING,
        "CHASE_JET": unified.CHASE_WAIT,
        "CHASE_FRESH": unified.CHASE_WAIT,
        "HALT": unified.HALTED,
    }
    _patch_state_and_attention(
        monkeypatch,
        states,
        jet={"CHASE_JET"},
        fresh={"CHASE_FRESH"},
        early={"DEV2"},
    )
    rows = [
        {"symbol": "CHASE_JET"},
        {"symbol": "DEV1"},
        {"symbol": "HALT"},
        {"symbol": "LOOK"},
        {"symbol": "CHASE_FRESH"},
        {"symbol": "DEV2"},
        {"symbol": "WATCH"},
    ]

    ordered = gs465.ordered_state_contiguous_records(
        rows, baseline_order=lambda items: list(items)
    )

    assert [row["symbol"] for row in ordered] == [
        "WATCH",
        "LOOK",
        "DEV2",
        "DEV1",
        "CHASE_JET",
        "CHASE_FRESH",
        "HALT",
    ]


def test_attention_remains_a_tiebreaker_inside_same_state(monkeypatch):
    states = {
        "PLAIN": unified.CHASE_WAIT,
        "TRAJ": unified.CHASE_WAIT,
        "JET": unified.CHASE_WAIT,
    }
    _patch_state_and_attention(
        monkeypatch,
        states,
        jet={"JET"},
        trajectory={"TRAJ"},
    )
    rows = [{"symbol": "PLAIN"}, {"symbol": "TRAJ"}, {"symbol": "JET"}]

    ordered = gs465.ordered_state_contiguous_records(
        rows, baseline_order=lambda items: list(items)
    )

    assert [row["symbol"] for row in ordered] == ["JET", "TRAJ", "PLAIN"]
    assert all(gs465.strict_state_band(row) == gs465.CHASE_WAIT_BAND for row in rows)


def _extreme_original(_record):
    return {
        "symbol": "HOT",
        "pct_change": 98.5,
        "vwap_distance_pct": 2.2,
        "vwap_relation": "above",
        "trend": True,
        "halted": False,
        "headline": "",
        "provenance": ("WEBULL_TOP_MOVER",),
        "label": "EXTREME MOVER · LOOK NOW",
        "guidance": "legacy",
    }


def test_extreme_percentage_move_alone_is_watch_not_look_now(monkeypatch):
    monkeypatch.setattr(
        unified,
        "opportunity_state",
        lambda _record: {
            "state": unified.CHASE_WAIT,
            "reason": "Price is extended.",
        },
    )
    event = gs465.cleaned_extreme_event(_extreme_original, {"symbol": "HOT"})
    assert event["label"] == "EXTREME MOVER · WATCH"
    assert "has not earned LOOK NOW" in event["guidance"]


def test_generic_market_attention_look_now_is_demoted_to_extreme_watch(monkeypatch):
    monkeypatch.setattr(
        unified,
        "opportunity_state",
        lambda _record: {
            "state": unified.LOOK_NOW,
            "reason": "A current attention trigger says this symbol deserves a chart review.",
        },
    )
    event = gs465.cleaned_extreme_event(_extreme_original, {"symbol": "HOT"})
    assert event["label"] == "EXTREME MOVER · WATCH"


def test_specific_structural_look_now_remains_look_now(monkeypatch):
    monkeypatch.setattr(
        unified,
        "opportunity_state",
        lambda _record: {
            "state": unified.LOOK_NOW,
            "reason": "1m ignition: SuperTrend turned bullish while price is holding above VWAP.",
        },
    )
    event = gs465.cleaned_extreme_event(_extreme_original, {"symbol": "HOT"})
    assert event["label"] == "EXTREME MOVER · LOOK NOW"
    assert "structure independently earned LOOK NOW" in event["guidance"]


def test_watch_for_entry_extreme_uses_truthful_label(monkeypatch):
    monkeypatch.setattr(
        unified,
        "opportunity_state",
        lambda _record: {
            "state": unified.WATCH_FOR_ENTRY,
            "reason": "VWAP, trend, participation, and expansion are aligned now.",
        },
    )
    event = gs465.cleaned_extreme_event(_extreme_original, {"symbol": "HOT"})
    assert event["label"] == "EXTREME MOVER · WATCH FOR ENTRY"


def test_do_not_chase_and_halt_labels_are_never_softened(monkeypatch):
    monkeypatch.setattr(
        unified,
        "opportunity_state",
        lambda _record: {"state": unified.DEVELOPING, "reason": "test"},
    )

    def do_not_chase(_record):
        event = _extreme_original(_record)
        event["label"] = "EXTREME MOVER · DO NOT CHASE"
        event["vwap_distance_pct"] = 8.0
        return event

    assert gs465.cleaned_extreme_event(do_not_chase, {})["label"] == "EXTREME MOVER · DO NOT CHASE"

    def halted(_record):
        event = _extreme_original(_record)
        event["label"] = "HALTED · WATCH RESUME"
        event["halted"] = True
        return event

    assert gs465.cleaned_extreme_event(halted, {})["label"] == "HALTED · WATCH RESUME"


def test_two_generic_extremes_keep_one_watch_banner_owner_for_continuity(monkeypatch):
    rows = [
        {"symbol": "BDRX", "pct_change": 81.8, "dollar_volume": 2_000_000},
        {"symbol": "TRUG", "pct_change": 78.7, "dollar_volume": 2_000_000},
    ]
    monkeypatch.setattr(
        unified,
        "opportunity_state",
        lambda record: {"state": unified.DEVELOPING, "reason": "test"},
    )

    def watch_event(record):
        return {
            "symbol": record["symbol"],
            "pct_change": record["pct_change"],
            "halted": False,
            "label": "EXTREME MOVER · WATCH",
        }

    monkeypatch.setattr(gs333, "extreme_market_event", watch_event)
    selected, event = gs465.prioritized_extreme_with_watch_continuity(
        lambda _rows: (None, None), rows
    )

    assert selected is rows[0]
    assert event["symbol"] == "BDRX"
    assert event["label"] == "EXTREME MOVER · WATCH"


def test_generic_extreme_watch_yields_to_non_extreme_actionable_setup(monkeypatch):
    rows = [
        {"symbol": "HOT", "pct_change": 90.0, "dollar_volume": 2_000_000},
        {"symbol": "SETUP", "pct_change": 20.0, "dollar_volume": 1_000_000},
    ]
    monkeypatch.setattr(
        unified,
        "opportunity_state",
        lambda record: {
            "state": unified.DEVELOPING,
            "reason": "test",
        },
    )

    def maybe_extreme(record):
        if record["symbol"] != "HOT":
            return None
        return {
            "symbol": "HOT",
            "pct_change": 90.0,
            "halted": False,
            "label": "EXTREME MOVER · WATCH",
        }

    monkeypatch.setattr(gs333, "extreme_market_event", maybe_extreme)
    assert gs465.prioritized_extreme_with_watch_continuity(
        lambda _rows: (None, None), rows
    ) == (None, None)


def test_gs465_is_last_at_the_final_presentation_boundary():
    source = Path("mide/gs414_final_enriched_opportunity_order.py").read_text(encoding="utf-8")
    assert "gs465_presentation_priority_cleanup" in source
    assert source.index("_install_gs462()") < source.index("_install_gs463()")
    assert source.index("_install_gs463()") < source.index("_install_gs465()")


def test_gs465_scope_lock_is_presentation_only():
    authority = Path("mide/authorities/presentation_audio.py").read_text(
        encoding="utf-8"
    )
    source = authority.split(
        "# Authoritative extreme-mover presentation semantics", 1
    )[1].split("FRESH_3M_SECONDS = 180.0", 1)[0]
    forbidden = (
        "qualified_for_entry =",
        "qualified_for_alert =",
        "qualified_for_watch =",
        "place_order(",
        "submit_order(",
        ".get_bars(",
        ".history(",
        "PARTICIPATION_MIN_",
        "NEAR_ST_LINE_PCT =",
        "LOOK_NOW_MAX_VWAP",
    )
    for token in forbidden:
        assert token not in source

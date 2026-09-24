from pathlib import Path

from mide import gs310_unified_opportunity_state as unified
from mide import gs457_maturation_leader_priority as gs457
from mide import gs459_price_trajectory_attention as gs459
from mide import gs462_preflip_ignition_watch as gs462
from mide import gs463_state_first_operator_order as gs463


def _patch_attention(monkeypatch, states, *, fresh=(), sustained=(), trajectory=(), early=(), jet=()):
    monkeypatch.setattr(
        unified,
        "opportunity_state",
        lambda record: {"state": states[record["symbol"]]},
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
    monkeypatch.setattr(
        gs462,
        "preflip_ignition_watch",
        lambda record: {
            "active": record["symbol"] in early or record["symbol"] in jet,
            "jet_fuel": record["symbol"] in jet,
        },
    )


def test_real_look_now_always_outranks_fresh_maturation_chase(monkeypatch):
    states = {"LOOK": unified.LOOK_NOW, "EXT": unified.CHASE_WAIT}
    _patch_attention(monkeypatch, states, fresh={"EXT"})
    rows = [{"symbol": "EXT"}, {"symbol": "LOOK"}]

    ordered = gs463.ordered_state_first_records(rows, baseline_order=lambda items: list(items))

    assert [row["symbol"] for row in ordered] == ["LOOK", "EXT"]
    assert gs463.effective_operator_attention_band(rows[1]) == gs463.LOOK_NOW_BAND
    assert gs463.effective_operator_attention_band(rows[0]) == gs463.FRESH_MATURATION_BAND


def test_real_look_now_outranks_jet_fuel_attention_only(monkeypatch):
    states = {"LOOK": unified.LOOK_NOW, "JET": unified.CHASE_WAIT}
    _patch_attention(monkeypatch, states, jet={"JET"})
    rows = [{"symbol": "JET"}, {"symbol": "LOOK"}]
    ordered = gs463.ordered_state_first_records(rows, baseline_order=lambda items: list(items))
    assert [row["symbol"] for row in ordered] == ["LOOK", "JET"]
    assert gs463.effective_operator_attention_band(rows[0]) == gs463.JET_FUEL_BAND


def test_attention_only_signals_still_outrank_ordinary_developing(monkeypatch):
    states = {"EARLY": unified.DEVELOPING, "DEV": unified.DEVELOPING}
    _patch_attention(monkeypatch, states, early={"EARLY"})
    rows = [{"symbol": "DEV"}, {"symbol": "EARLY"}]
    ordered = gs463.ordered_state_first_records(rows, baseline_order=lambda items: list(items))
    assert [row["symbol"] for row in ordered] == ["EARLY", "DEV"]


def test_developing_stays_above_ordinary_chase(monkeypatch):
    states = {"DEV": unified.DEVELOPING, "CHASE": unified.CHASE_WAIT}
    _patch_attention(monkeypatch, states)
    rows = [{"symbol": "CHASE"}, {"symbol": "DEV"}]
    ordered = gs463.ordered_state_first_records(rows, baseline_order=lambda items: list(items))
    assert [row["symbol"] for row in ordered] == ["DEV", "CHASE"]


def test_watch_for_entry_remains_highest(monkeypatch):
    states = {"WATCH": unified.WATCH_FOR_ENTRY, "LOOK": unified.LOOK_NOW}
    _patch_attention(monkeypatch, states)
    rows = [{"symbol": "LOOK"}, {"symbol": "WATCH"}]
    ordered = gs463.ordered_state_first_records(rows, baseline_order=lambda items: list(items))
    assert [row["symbol"] for row in ordered] == ["WATCH", "LOOK"]


def test_equal_band_preserves_complete_baseline_order(monkeypatch):
    states = {"B": unified.LOOK_NOW, "A": unified.LOOK_NOW}
    _patch_attention(monkeypatch, states)
    rows = [{"symbol": "A"}, {"symbol": "B"}]
    ordered = gs463.ordered_state_first_records(
        rows,
        baseline_order=lambda _items: [{"symbol": "B"}, {"symbol": "A"}],
    )
    assert [row["symbol"] for row in ordered] == ["B", "A"]


def test_gs463_is_reasserted_outside_gs462_at_final_presentation_boundary():
    source = Path("mide/gs414_final_enriched_opportunity_order.py").read_text(encoding="utf-8")
    assert "gs463_state_first_operator_order" in source
    assert source.index("_install_gs462()") < source.index("_install_gs463()")


def test_gs463_scope_lock_is_presentation_order_only():
    source = Path("mide/authorities/presentation_audio.py").read_text(encoding="utf-8")
    start = source.index("# Authoritative operator ordering")
    end = source.index("# GS527 explosive 30s operator-attention watch", start)
    block = source[start:end]
    forbidden = (
        "qualified_for_entry =",
        "qualified_for_alert =",
        "qualified_for_watch =",
        "place_order(",
        "submit_order(",
        ".get_bars(",
        ".history(",
        "PARTICIPATION_MIN_",
        "LOOK_NOW_MAX_VWAP",
    )
    for token in forbidden:
        assert token not in block

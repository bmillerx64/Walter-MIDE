from __future__ import annotations

from pathlib import Path

from mide import gs310_unified_opportunity_state as unified
from mide import gs460_st_flip_compression_ignition as gs460
from mide import gs474_fresh_look_now_expiry as gs474


def _look_now(*, compression=True):
    state = {
        "state": unified.LOOK_NOW,
        "color": unified.STATE_COLORS[unified.LOOK_NOW],
        "reason": "Open the chart now.",
        "next_step": "Investigate.",
        "attention_provenance": [],
    }
    if compression:
        state["attention_provenance"] = ["ST_FLIP_PRICE_COMPRESSION"]
        state["st_flip_compression"] = {"active": True, "fresh_join": True}
    return state


def test_stale_compression_look_now_expires_to_developing(monkeypatch):
    monkeypatch.setattr(
        gs460,
        "st_flip_compression",
        lambda record: {"active": True, "fresh_join": False, "depth": 2},
    )

    state = gs474.fresh_look_now_state(lambda record: _look_now(), {"symbol": "MGN"})

    assert state["state"] == unified.DEVELOPING
    assert "no longer a fresh transition" in state["reason"]
    assert state["gs474_look_now_freshness"]["fresh_join"] is False
    assert state["gs474_look_now_freshness"]["entry_authority_changed"] is False
    assert state["gs474_look_now_freshness"]["alert_authority_changed"] is False


def test_fresh_compression_look_now_is_preserved(monkeypatch):
    base = _look_now()
    monkeypatch.setattr(
        gs460,
        "st_flip_compression",
        lambda record: {"active": True, "fresh_join": True, "depth": 2},
    )

    state = gs474.fresh_look_now_state(lambda record: base, {"symbol": "MGN"})

    assert state is base
    assert state["state"] == unified.LOOK_NOW


def test_other_look_now_sources_are_untouched(monkeypatch):
    base = _look_now(compression=False)

    def should_not_run(record):
        raise AssertionError("GS460 should not be consulted for unrelated LOOK NOW")

    monkeypatch.setattr(gs460, "st_flip_compression", should_not_run)
    state = gs474.fresh_look_now_state(lambda record: base, {"symbol": "NEWS"})

    assert state is base
    assert state["state"] == unified.LOOK_NOW


def test_non_look_now_state_is_untouched(monkeypatch):
    base = {
        "state": unified.CHASE_WAIT,
        "color": unified.STATE_COLORS[unified.CHASE_WAIT],
        "attention_provenance": ["ST_FLIP_PRICE_COMPRESSION"],
    }

    def should_not_run(record):
        raise AssertionError("GS460 should not be consulted for non-LOOK NOW")

    monkeypatch.setattr(gs460, "st_flip_compression", should_not_run)
    state = gs474.fresh_look_now_state(lambda record: base, {"symbol": "DLXY"})

    assert state is base
    assert state["state"] == unified.CHASE_WAIT


def test_gs474_is_after_gs468_at_final_state_boundary():
    source = Path("mide/gs414_final_enriched_opportunity_order.py").read_text(encoding="utf-8")
    assert "gs474_fresh_look_now_expiry" in source
    assert source.index("_install_gs468()") < source.index("_install_gs474()")


def test_gs474_scope_lock_is_presentation_urgency_only():
    source = Path("mide/gs474_fresh_look_now_expiry.py").read_text(encoding="utf-8")
    forbidden = (
        "qualified_for_entry =",
        "qualified_for_alert =",
        "qualified_for_watch =",
        "execute_order",
        "place_order",
        "get_bars(",
        "get_history(",
        "fetch_bars(",
    )
    for token in forbidden:
        assert token not in source

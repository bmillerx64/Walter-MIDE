from pathlib import Path

from mide import gs310_unified_opportunity_state as unified
from mide import gs467_look_now_semantic_consolidation as gs467


def _look(reason: str):
    return {
        "state": unified.LOOK_NOW,
        "color": unified.STATE_COLORS[unified.LOOK_NOW],
        "reason": reason,
        "next_step": "Open the chart now.",
        "attention_provenance": ["TEST"],
    }


def _weak_urgency(*, early=False, jet=False, compression=False):
    return {
        "compression": {"active": compression},
        "preflip": {"active": early or jet, "jet_fuel": jet},
        "strong": bool(compression or jet),
    }


def test_fngr_shape_standalone_1m_ignition_is_developing_not_look_now(monkeypatch):
    monkeypatch.setattr(gs467, "bottom_up_urgency", lambda _record: _weak_urgency())
    view = gs467.consolidated_look_now(
        lambda _record: _look(
            "1m ignition: price freshly reclaimed/held VWAP while 1m SuperTrend is bullish."
        ),
        {"symbol": "FNGR"},
    )

    assert view["state"] == unified.DEVELOPING
    assert "has not yet earned LOOK NOW" in view["reason"]
    assert view["look_now_semantics"]["legacy_reason_demoted"] is True


def test_generic_current_attention_no_longer_manufactures_look_now(monkeypatch):
    monkeypatch.setattr(gs467, "bottom_up_urgency", lambda _record: _weak_urgency())
    view = gs467.consolidated_look_now(
        lambda _record: _look(
            "A current attention trigger says this symbol deserves a chart review."
        ),
        {"symbol": "ATTN"},
    )
    assert view["state"] == unified.DEVELOPING
    assert "Current 1m/attention evidence" in view["reason"]


def test_30s_1m_early_watch_stays_visible_but_does_not_keep_look_now(monkeypatch):
    monkeypatch.setattr(
        gs467,
        "bottom_up_urgency",
        lambda _record: _weak_urgency(early=True),
    )
    view = gs467.consolidated_look_now(
        lambda _record: _look(
            "1m ignition: SuperTrend turned bullish while price is holding above VWAP."
        ),
        {"symbol": "EARLY"},
    )
    assert view["state"] == unified.DEVELOPING
    assert view["reason"].startswith("EARLY WATCH:")
    assert view["look_now_semantics"]["early_watch"] is True


def test_3m_jet_fuel_may_retain_existing_look_now(monkeypatch):
    monkeypatch.setattr(
        gs467,
        "bottom_up_urgency",
        lambda _record: _weak_urgency(early=True, jet=True),
    )
    original = _look(
        "1m ignition: price freshly reclaimed/held VWAP while 1m SuperTrend is bullish."
    )
    view = gs467.consolidated_look_now(lambda _record: original, {"symbol": "JET"})
    assert view is original
    assert view["state"] == unified.LOOK_NOW


def test_30s_1m_flip_compression_may_retain_existing_look_now(monkeypatch):
    monkeypatch.setattr(
        gs467,
        "bottom_up_urgency",
        lambda _record: _weak_urgency(compression=True),
    )
    original = _look(
        "1m ignition: SuperTrend turned bullish while price is holding above VWAP."
    )
    view = gs467.consolidated_look_now(lambda _record: original, {"symbol": "COMP"})
    assert view is original


def test_specific_structural_look_now_reasons_are_untouched(monkeypatch):
    monkeypatch.setattr(gs467, "bottom_up_urgency", lambda _record: _weak_urgency())
    reasons = (
        "Reset/retest: a current Webull mover returned to the near-VWAP window.",
        "Consolidation re-arm: 1m SuperTrend flipped bullish after a compressed reset.",
        "ST/VWAP maturation reached 3M; 30s -> 1m -> 3m.",
        "IGNITION BUILDING: 30s -> 1m -> 3m ST flip prices are compressed within 3.0% with supporting flow.",
    )
    for reason in reasons:
        original = _look(reason)
        assert gs467.consolidated_look_now(lambda _record, item=original: item, {}) is original


def test_non_look_now_states_are_never_changed(monkeypatch):
    monkeypatch.setattr(gs467, "bottom_up_urgency", lambda _record: _weak_urgency())
    for state in (unified.WATCH_FOR_ENTRY, unified.DEVELOPING, unified.CHASE_WAIT, unified.HALTED):
        original = {"state": state, "reason": "test"}
        assert gs467.consolidated_look_now(lambda _record, item=original: item, {}) is original


def test_gs467_is_final_state_semantic_boundary_after_gs466():
    source = Path("mide/gs414_final_enriched_opportunity_order.py").read_text(encoding="utf-8")
    assert "gs467_look_now_semantic_consolidation" in source
    assert source.index("_install_gs466()") < source.index("_install_gs467()")


def test_gs467_scope_lock_is_presentation_only():
    source = Path("mide/gs467_look_now_semantic_consolidation.py").read_text(encoding="utf-8")
    forbidden = (
        "qualified_for_entry =",
        "qualified_for_alert =",
        "qualified_for_watch =",
        "place_order(",
        "submit_order(",
        ".get_bars(",
        ".history(",
        "NEAR_ST_LINE_PCT =",
        "LOOK_NOW_MAX_VWAP",
        "PARTICIPATION_MIN_",
    )
    for token in forbidden:
        assert token not in source

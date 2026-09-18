from __future__ import annotations

from pathlib import Path

from mide import gs495_extreme_look_now_reset_language as gs495


def _event(label, distance):
    return {
        "symbol": "SSM",
        "pct_change": 82.9,
        "vwap_distance_pct": distance,
        "label": label,
        "guidance": "legacy",
    }


def test_ssm_style_structural_look_now_at_4_4_pct_becomes_watch_reset():
    record = {"symbol": "SSM", "vwap_distance_pct": 4.4}
    result = gs495.refine_extreme_event(
        lambda _record: _event("EXTREME MOVER · LOOK NOW", 4.4),
        record,
    )
    assert result["label"] == "EXTREME MOVER · LOOK NOW · WATCH RESET"
    assert "4.4% above VWAP" in result["guidance"]
    assert "2% fresh-ignition location band" in result["guidance"]
    assert "LOOK NOW is attention, not entry permission" in result["guidance"]
    assert result["entry_authority_changed"] is False
    assert result["anti_chase_authority_changed"] is False


def test_fresh_location_inside_two_percent_preserves_plain_look_now():
    event = _event("EXTREME MOVER · LOOK NOW", 1.8)
    result = gs495.refine_extreme_event(lambda _record: event, {"symbol": "SSM"})
    assert result is event
    assert result["label"] == "EXTREME MOVER · LOOK NOW"


def test_existing_do_not_chase_semantics_always_win():
    event = _event("EXTREME MOVER · DO NOT CHASE", 7.2)
    result = gs495.refine_extreme_event(lambda _record: event, {"symbol": "SSM"})
    assert result is event
    assert result["label"] == "EXTREME MOVER · DO NOT CHASE"


def test_generic_watch_is_not_promoted_or_rewritten():
    event = _event("EXTREME MOVER · WATCH", 3.8)
    result = gs495.refine_extreme_event(lambda _record: event, {"symbol": "SSM"})
    assert result is event


def test_halted_semantics_are_untouched():
    event = _event("HALTED · WATCH RESUME", 3.0)
    result = gs495.refine_extreme_event(lambda _record: event, {"symbol": "QNME"})
    assert result is event


def test_gs495_installs_after_gs493_at_final_late_boundary():
    source = Path("mide/gs414_final_enriched_opportunity_order.py").read_text(
        encoding="utf-8"
    )
    body = source.split("def install() -> None:", 1)[1]
    assert "_install_gs495()" in body
    assert body.index("_install_gs493()") < body.index("_install_gs495()")


def test_scope_lock_is_presentation_only():
    source = Path("mide/gs495_extreme_look_now_reset_language.py").read_text(
        encoding="utf-8"
    )
    forbidden = (
        "qualified_for_entry =",
        "qualified_for_alert =",
        "opportunity_score =",
        "conviction_score =",
        "place_order(",
        "submit_order(",
        "execute_order(",
    )
    assert not any(token in source for token in forbidden)
    assert "entry_authority_changed" in source
    assert "anti_chase_authority_changed" in source

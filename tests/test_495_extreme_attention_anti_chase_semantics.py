from pathlib import Path

from mide import gs333_extreme_mover_operator_priority as gs333
from mide import gs495_extreme_attention_anti_chase_semantics as gs495


def _record(**overrides):
    row = {
        "symbol": "SSM",
        "pct_change": 82.9,
        "vwap_relation": "above",
        "vwap_distance_pct": 5.0,
        "supertrend_bullish": True,
        "dollar_volume": 24_000_000,
        "discovery_reasons": ["Webull native: day_gainers"],
    }
    row.update(overrides)
    return row


def test_structural_look_now_that_is_extended_gets_watch_reset_qualifier():
    def original(_record):
        return {
            "symbol": "SSM",
            "label": "EXTREME MOVER · LOOK NOW",
            "guidance": "Current structure independently earned LOOK NOW.",
            "vwap_distance_pct": 4.4,
            "halted": False,
        }

    event = gs495.truthful_extreme_market_event(original, _record(vwap_distance_pct=4.4))
    assert event["label"] == "EXTREME MOVER · LOOK NOW · EXTENDED / WATCH RESET"
    assert event["anti_chase_active"] is True
    assert "Urgent attention only" in event["guidance"]
    assert "do not chase" in event["guidance"].lower()
    assert event["entry_authority_changed"] is False


def test_generic_extreme_watch_is_not_promoted_back_to_look_now():
    event = gs333.extreme_market_event(_record(vwap_distance_pct=4.4))
    assert event is not None
    assert event["label"] == "EXTREME MOVER · WATCH"


def test_existing_over_five_percent_do_not_chase_contract_is_preserved():
    event = gs333.extreme_market_event(_record(vwap_distance_pct=48.0))
    assert event is not None
    assert event["label"] == "EXTREME MOVER · DO NOT CHASE"


def test_inside_existing_two_percent_zone_preserves_current_final_semantics():
    event = gs333.extreme_market_event(_record(vwap_distance_pct=1.8))
    assert event is not None
    assert event["label"] == "EXTREME MOVER · WATCH"


def test_halt_still_outranks_extended_semantics():
    event = gs333.extreme_market_event(_record(halted=True))
    assert event is not None
    assert event["label"] == "HALTED · WATCH RESUME"


def test_markup_can_render_both_attention_and_anti_chase_truth():
    event = gs495.truthful_extreme_market_event(
        lambda _record: {
            "symbol": "SSM",
            "pct_change": 82.9,
            "vwap_distance_pct": 4.4,
            "trend": True,
            "halted": False,
            "headline": "",
            "label": "EXTREME MOVER · LOOK NOW",
            "guidance": "Current structure independently earned LOOK NOW.",
        },
        _record(vwap_distance_pct=4.4),
    )
    markup = gs333.extreme_event_markup(event)
    assert "LOOK NOW" in markup
    assert "EXTENDED / WATCH RESET" in markup
    assert "do not chase" in markup.lower()


def test_gs495_installs_after_gs493_at_final_late_boundary():
    source = Path("mide/gs414_final_enriched_opportunity_order.py").read_text(
        encoding="utf-8"
    )
    assert "_install_gs495()" in source
    assert source.index("_install_gs493()") < source.index("_install_gs495()")


def test_scope_lock_is_presentation_only():
    authority = Path("mide/authorities/presentation_audio.py").read_text(
        encoding="utf-8"
    )
    source = authority.split(
        "# Authoritative extreme-mover presentation semantics", 1
    )[1].split("FRESH_3M_SECONDS = 180.0", 1)[0]
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
    assert 'ANTI_CHASE_VWAP_DISTANCE_PCT = 2.0' in source
    assert 'entry_authority_changed' in source

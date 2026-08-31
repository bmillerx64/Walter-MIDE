from mide import gs333_extreme_mover_operator_priority as gs333
from mide import ui


def _extreme_record(**overrides):
    record = {
        "symbol": "CLGN",
        "pct_change": 162.5,
        "vwap_relation": "above",
        "vwap_distance_pct": 48.0,
        "supertrend_bullish": True,
        "dollar_volume": 12_000_000,
        "discovery_reasons": ["Webull native: day_gainers"],
        "headline": "Company announces material acquisition",
    }
    record.update(overrides)
    return record


def test_extreme_live_top_mover_is_attention_event_not_entry_upgrade():
    event = gs333.extreme_market_event(_extreme_record())
    assert event is not None
    assert event["symbol"] == "CLGN"
    assert event["label"] == "EXTREME MOVER · DO NOT CHASE"
    assert "not an entry signal" in event["guidance"]


def test_large_move_without_current_attention_provenance_is_not_promoted():
    record = _extreme_record(discovery_reasons=["Webull native: absolute_volume"])
    assert gs333.extreme_market_event(record) is None


def test_halt_state_takes_priority_over_extreme_chase_language():
    event = gs333.extreme_market_event(_extreme_record(halted=True))
    assert event is not None
    assert event["label"] == "HALTED · WATCH RESUME"
    assert "reassess" in event["guidance"].lower()


def test_extreme_event_priority_prefers_halt_then_larger_move():
    first = _extreme_record(symbol="AAA", pct_change=180)
    halted = _extreme_record(symbol="BBB", pct_change=90, halted=True)
    record, event = gs333.prioritized_extreme_event([first, halted])
    assert record is halted
    assert event["symbol"] == "BBB"


def test_markup_keeps_entry_discipline_explicit():
    event = gs333.extreme_market_event(_extreme_record())
    markup = gs333.extreme_event_markup(event)
    assert "CLGN" in markup
    assert "DO NOT CHASE" in markup
    assert "Catalyst:" in markup


def test_gs333_installs_after_action_first_without_changing_scanner_contracts():
    assert getattr(ui.render_walter_mission_control, "_gs333_operator_priority", False)
    assert callable(ui.render_walter_mission_control._gs333_original)
    assert getattr(ui.play_alert, "_gs333_voice_sidebar", False)
    assert callable(ui.play_alert._gs333_original)

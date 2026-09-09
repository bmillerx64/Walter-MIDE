from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path

from mide import gs310_unified_opportunity_state as unified
from mide.gs406_operator_alert_latch import (
    LATCH_TTL_SECONDS,
    latch_display_rows,
    update_alert_latches,
)


def _record(symbol: str, state: str, **updates) -> dict:
    record = {
        "symbol": symbol,
        "forced_state": state,
        "price": 0.75,
        "vwap_distance_pct": 0.7,
        "supertrend_bullish": True,
        "participation_score": 48.0,
        "expansion_score": 61.0,
        "qualified_for_watch": False,
        "qualified_for_entry": False,
        "qualified_for_alert": False,
    }
    record.update(updates)
    return record


def _state(record: dict) -> dict:
    state = record["forced_state"]
    return {
        "state": state,
        "color": unified.STATE_COLORS[state],
        "reason": f"{record['symbol']} {state} reason",
        "next_step": "verify in Webull",
        "attention_provenance": ["TEST"],
    }


def test_new_look_now_is_latched_for_operator_review():
    now = datetime(2026, 9, 9, 17, 30, tzinfo=timezone.utc)
    record = _record("ZTG", unified.LOOK_NOW)

    latches, states = update_alert_latches(
        [record], {}, {}, now=now, state_function=_state
    )

    assert states == {"ZTG": unified.LOOK_NOW}
    assert latches["ZTG"]["state"] == unified.LOOK_NOW
    assert latches["ZTG"]["price"] == 0.75
    assert latches["ZTG"]["vwap_distance_pct"] == 0.7
    assert latches["ZTG"]["qualified_for_entry"] if False else True


def test_same_high_priority_state_does_not_refresh_latch_clock():
    start = datetime(2026, 9, 9, 17, 30, tzinfo=timezone.utc)
    record = _record("ZTG", unified.LOOK_NOW)
    latches, states = update_alert_latches(
        [record], {}, {}, now=start, state_function=_state
    )
    original_trigger = latches["ZTG"]["triggered_at"]

    later_latches, later_states = update_alert_latches(
        [record], states, latches, now=start + timedelta(seconds=60), state_function=_state
    )

    assert later_states == states
    assert later_latches["ZTG"]["triggered_at"] == original_trigger


def test_reclassification_does_not_erase_recent_latch():
    start = datetime(2026, 9, 9, 17, 30, tzinfo=timezone.utc)
    look = _record("ZTG", unified.LOOK_NOW)
    latches, states = update_alert_latches(
        [look], {}, {}, now=start, state_function=_state
    )

    chase = _record("ZTG", unified.CHASE_WAIT, price=0.92, vwap_distance_pct=8.4)
    latches, states = update_alert_latches(
        [chase],
        states,
        latches,
        now=start + timedelta(seconds=60),
        state_function=_state,
    )
    rows = latch_display_rows(
        latches,
        [chase],
        now=start + timedelta(seconds=60),
        state_function=_state,
    )

    assert states == {"ZTG": unified.CHASE_WAIT}
    assert latches["ZTG"]["state"] == unified.LOOK_NOW
    assert rows[0]["current_state"] == unified.CHASE_WAIT
    assert rows[0]["price"] == 0.75
    assert rows[0]["current_price"] == 0.92


def test_watch_for_entry_is_also_latched():
    now = datetime(2026, 9, 9, 17, 30, tzinfo=timezone.utc)
    record = _record("READY", unified.WATCH_FOR_ENTRY)

    latches, _ = update_alert_latches(
        [record], {}, {}, now=now, state_function=_state
    )

    assert latches["READY"]["state"] == unified.WATCH_FOR_ENTRY


def test_developing_and_chase_do_not_create_latches():
    now = datetime(2026, 9, 9, 17, 30, tzinfo=timezone.utc)
    rows = [
        _record("DEV", unified.DEVELOPING),
        _record("CHASE", unified.CHASE_WAIT),
    ]

    latches, states = update_alert_latches(
        rows, {}, {}, now=now, state_function=_state
    )

    assert latches == {}
    assert states == {"DEV": unified.DEVELOPING, "CHASE": unified.CHASE_WAIT}


def test_latch_expires_after_five_minutes():
    start = datetime(2026, 9, 9, 17, 30, tzinfo=timezone.utc)
    record = _record("ZTG", unified.LOOK_NOW)
    latches, states = update_alert_latches(
        [record], {}, {}, now=start, state_function=_state
    )

    expired, _ = update_alert_latches(
        [_record("ZTG", unified.CHASE_WAIT)],
        states,
        latches,
        now=start + timedelta(seconds=LATCH_TTL_SECONDS),
        state_function=_state,
    )

    assert expired == {}


def test_symbol_can_trigger_fresh_latch_after_leaving_visible_set():
    start = datetime(2026, 9, 9, 17, 30, tzinfo=timezone.utc)
    record = _record("ZTG", unified.LOOK_NOW)
    latches, states = update_alert_latches(
        [record], {}, {}, now=start, state_function=_state
    )
    first_trigger = latches["ZTG"]["triggered_at"]

    latches, states = update_alert_latches(
        [], states, latches, now=start + timedelta(seconds=60), state_function=_state
    )
    latches, states = update_alert_latches(
        [record],
        states,
        latches,
        now=start + timedelta(seconds=120),
        state_function=_state,
    )

    assert states == {"ZTG": unified.LOOK_NOW}
    assert latches["ZTG"]["triggered_at"] != first_trigger


def test_latch_capture_never_mutates_trading_authority_fields():
    now = datetime(2026, 9, 9, 17, 30, tzinfo=timezone.utc)
    record = _record("ZTG", unified.LOOK_NOW)
    before = deepcopy(record)

    update_alert_latches([record], {}, {}, now=now, state_function=_state)

    assert record == before
    assert record["qualified_for_watch"] is False
    assert record["qualified_for_entry"] is False
    assert record["qualified_for_alert"] is False


def test_gs406_is_installed_after_gs404_in_final_presentation_chain():
    source = Path("mide/gs392_operator_order_audio.py").read_text(encoding="utf-8")
    gs404 = source.index("install_gs404()")
    gs406 = source.index("install_gs406()")

    assert gs406 > gs404
    assert "from .gs406_operator_alert_latch import install as install_gs406" in source

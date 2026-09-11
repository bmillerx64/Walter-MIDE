from mide import gs310_unified_opportunity_state as unified
from mide import gs333_extreme_mover_operator_priority as extreme
from mide import gs393_ignition_truth_extreme_decay as gs393


def _record(symbol, state, *, label=None, pct_change=90.0, halted=False):
    return {
        "symbol": symbol,
        "test_state": state,
        "test_event_label": label,
        "test_pct_change": pct_change,
        "test_halted": halted,
        "dollar_volume": 1_000_000,
    }


def _fake_event(record):
    label = record.get("test_event_label")
    if not label:
        return None
    return {
        "symbol": record["symbol"],
        "pct_change": record.get("test_pct_change", 90.0),
        "vwap_distance_pct": 15.0 if "DO NOT CHASE" in label else 1.0,
        "vwap_relation": "above",
        "trend": True,
        "halted": bool(record.get("test_halted")),
        "headline": "catalyst",
        "provenance": ("WEBULL_TOP_MOVER",),
        "label": label,
        "guidance": "test",
    }


def _state(record):
    return {"state": record["test_state"]}


def test_gs439_fresh_do_not_chase_yields_to_developing(monkeypatch):
    gs393.reset_state()
    monkeypatch.setattr(extreme, "extreme_market_event", _fake_event)
    monkeypatch.setattr(unified, "opportunity_state", _state)

    selected, event = extreme.prioritized_extreme_event(
        [
            _record("BDRX", unified.CHASE_WAIT, label="EXTREME MOVER · DO NOT CHASE"),
            _record("TRUG", unified.DEVELOPING),
        ],
        now=100.0,
    )

    assert selected is None
    assert event is None
    gs393.reset_state()


def test_gs439_fresh_do_not_chase_yields_to_look_now_and_watch_for_entry(monkeypatch):
    gs393.reset_state()
    monkeypatch.setattr(extreme, "extreme_market_event", _fake_event)
    monkeypatch.setattr(unified, "opportunity_state", _state)

    for higher_state in (unified.LOOK_NOW, unified.WATCH_FOR_ENTRY):
        selected, event = extreme.prioritized_extreme_event(
            [
                _record("BDRX", unified.CHASE_WAIT, label="EXTREME MOVER · DO NOT CHASE"),
                _record("WORK", higher_state),
            ],
            now=100.0,
        )
        assert selected is None
        assert event is None

    gs393.reset_state()


def test_gs439_do_not_chase_can_lead_when_everything_else_is_chase_wait(monkeypatch):
    gs393.reset_state()
    monkeypatch.setattr(extreme, "extreme_market_event", _fake_event)
    monkeypatch.setattr(unified, "opportunity_state", _state)

    selected, event = extreme.prioritized_extreme_event(
        [
            _record("BDRX", unified.CHASE_WAIT, label="EXTREME MOVER · DO NOT CHASE"),
            _record("OTHER", unified.CHASE_WAIT),
        ],
        now=100.0,
    )

    assert selected["symbol"] == "BDRX"
    assert event["label"] == "EXTREME MOVER · DO NOT CHASE"
    gs393.reset_state()


def test_gs439_halted_and_extreme_look_now_keep_immediate_priority(monkeypatch):
    gs393.reset_state()
    monkeypatch.setattr(extreme, "extreme_market_event", _fake_event)
    monkeypatch.setattr(unified, "opportunity_state", _state)

    halted, halted_event = extreme.prioritized_extreme_event(
        [
            _record("HALT", unified.HALTED, label="HALTED · WATCH RESUME", halted=True),
            _record("DEV", unified.DEVELOPING),
        ],
        now=100.0,
    )
    assert halted["symbol"] == "HALT"
    assert "HALTED" in halted_event["label"]

    gs393.reset_state()
    look, look_event = extreme.prioritized_extreme_event(
        [
            _record("HOT", unified.LOOK_NOW, label="EXTREME MOVER · LOOK NOW"),
            _record("DEV", unified.DEVELOPING),
        ],
        now=100.0,
    )
    assert look["symbol"] == "HOT"
    assert "LOOK NOW" in look_event["label"]
    gs393.reset_state()


def test_gs439_rebinds_retained_pre_gs439_decay_wrapper(monkeypatch):
    def stale_wrapper(records, *, now=None):
        return None, None

    stale_wrapper._gs393_extreme_decay = True
    monkeypatch.setattr(extreme, "prioritized_extreme_event", stale_wrapper)

    gs393._install_extreme_banner_decay()

    rebound = extreme.prioritized_extreme_event
    assert rebound is not stale_wrapper
    assert rebound._gs393_extreme_decay is True
    assert rebound._gs439_action_first_extreme is True

from pathlib import Path

from mide import gs310_unified_opportunity_state as unified
from mide import gs363_operator_attention_hierarchy as gs363
from mide import gs369_escalation_priority_order as gs369
from mide import gs455_early_ignition_3m_confirmation as gs455
from mide import gs457_maturation_leader_priority as gs457
from mide import ui


def _progression(*, recent_higher=(), newest=None):
    active = ["1m"]
    events = {
        "1m": {
            "crossed": True,
            "current_confirmed": True,
            "recent": True,
            "new": newest == "1m",
            "age_seconds": 60.0,
        }
    }
    for index, label in enumerate(recent_higher, start=1):
        active.append(label)
        events[label] = {
            "crossed": True,
            "current_confirmed": True,
            "recent": True,
            "new": newest == label,
            "age_seconds": 60.0 + index,
        }
    return {
        "active_rungs": active,
        "events": events,
        "ordered": True,
        "latest_new_rung": newest,
        "stage": (
            "PERSISTENCE"
            if any(label in recent_higher for label in ("5m", "10m", "15m"))
            else ("CONFIRMATION" if "3m" in recent_higher else "IGNITION")
        ),
        "sequence": " -> ".join(active),
    }


def _record(symbol, state, *, progression=None, signal=False, flow=False, attention=0):
    return {
        "symbol": symbol,
        "_state": state,
        "_progression": progression or _progression(),
        "_signal": signal,
        "_flow": flow,
        "_attention": attention,
    }


def _patch_runtime(monkeypatch):
    monkeypatch.setattr(
        unified,
        "opportunity_state",
        lambda record: {"state": record["_state"]},
    )
    monkeypatch.setattr(
        gs455,
        "crossover_progression",
        lambda record: record["_progression"],
    )
    monkeypatch.setattr(
        gs455,
        "progression_signal",
        lambda record: {
            "active": bool(record["_signal"]),
            "new_rung": record["_progression"].get("latest_new_rung"),
        },
    )
    monkeypatch.setattr(gs455, "_supporting_flow", lambda record: bool(record["_flow"]))
    monkeypatch.setattr(
        ui,
        "trader_priority_sort_key",
        lambda record: (int(record.get("_attention", 0)),),
    )
    monkeypatch.setattr(
        gs363,
        "operator_attention_score",
        lambda record: int(record.get("_attention", 0)),
    )


def test_fresh_maturation_leader_ranks_below_entry_but_above_ordinary_look_now(monkeypatch):
    _patch_runtime(monkeypatch)
    records = [
        _record("LOOK", unified.LOOK_NOW, attention=90),
        _record(
            "FRESH",
            unified.CHASE_WAIT,
            progression=_progression(recent_higher=("3m",), newest="3m"),
            signal=True,
            flow=True,
            attention=20,
        ),
        _record(
            "READY",
            unified.WATCH_FOR_ENTRY,
            progression=_progression(recent_higher=("3m",), newest="3m"),
            signal=True,
            flow=True,
            attention=10,
        ),
    ]

    ordered = gs457.ordered_maturation_records(records)
    assert [record["symbol"] for record in ordered] == ["READY", "FRESH", "LOOK"]


def test_recent_confirmed_3m_leader_stays_above_developing_after_new_window_expires(monkeypatch):
    _patch_runtime(monkeypatch)
    recent = _record(
        "RETO",
        unified.CHASE_WAIT,
        progression=_progression(recent_higher=("3m",)),
        signal=False,
        flow=True,
        attention=5,
    )
    developing = _record("DEV", unified.DEVELOPING, attention=99)

    detail = gs457.maturation_attention(recent)
    assert detail["fresh_maturation"] is False
    assert detail["sustained_confirmation"] is True
    assert detail["reason"] == "recent_3m_plus_confirmation"

    ordered = gs457.ordered_maturation_records([developing, recent])
    assert [record["symbol"] for record in ordered] == ["RETO", "DEV"]


def test_recent_confirmation_still_ranks_below_real_look_now(monkeypatch):
    _patch_runtime(monkeypatch)
    recent = _record(
        "FBDT",
        unified.CHASE_WAIT,
        progression=_progression(recent_higher=("3m", "5m")),
        flow=True,
        attention=100,
    )
    look = _record("LOOK", unified.LOOK_NOW, attention=1)

    ordered = gs457.ordered_maturation_records([recent, look])
    assert [record["symbol"] for record in ordered] == ["LOOK", "FBDT"]


def test_1m_only_or_missing_flow_does_not_override_developing(monkeypatch):
    _patch_runtime(monkeypatch)
    one_minute = _record(
        "ONE",
        unified.CHASE_WAIT,
        progression=_progression(),
        signal=False,
        flow=True,
        attention=100,
    )
    no_flow = _record(
        "NOFLOW",
        unified.CHASE_WAIT,
        progression=_progression(recent_higher=("3m",)),
        signal=False,
        flow=False,
        attention=100,
    )
    developing = _record("DEV", unified.DEVELOPING, attention=1)

    ordered = gs457.ordered_maturation_records([one_minute, no_flow, developing])
    assert ordered[0]["symbol"] == "DEV"


def test_halted_never_receives_maturation_priority(monkeypatch):
    _patch_runtime(monkeypatch)
    halted = _record(
        "HALT",
        unified.HALTED,
        progression=_progression(recent_higher=("3m",), newest="3m"),
        signal=True,
        flow=True,
        attention=100,
    )
    detail = gs457.maturation_attention(halted)
    assert detail["fresh_maturation"] is False
    assert detail["sustained_confirmation"] is False
    assert detail["band"] == gs457.HALTED_BAND


def test_gs457_installer_hard_binds_final_order_and_is_idempotent(monkeypatch):
    def baseline(records):
        return list(records)

    monkeypatch.setattr(gs369, "ordered_escalation_records", baseline)
    gs457.install()
    installed = gs369.ordered_escalation_records
    assert installed is not baseline
    assert getattr(installed, "_gs457_maturation_leader_priority", False) is True

    gs457.install()
    assert gs369.ordered_escalation_records is installed


def test_gs457_chains_after_gs456_on_cold_and_warm_runtime_paths():
    source = Path("mide/gs454_flight_recorder_download_freshness.py").read_text(
        encoding="utf-8"
    )
    assert "gs457_maturation_leader_priority" in source
    assert source.count("_install_gs457()") >= 2


def test_gs457_scope_lock_is_presentation_only():
    source = Path("mide/gs457_maturation_leader_priority.py").read_text(
        encoding="utf-8"
    )
    forbidden = (
        "qualified_for_entry =",
        "qualified_for_alert =",
        "qualified_for_watch =",
        "place_order(",
        "submit_order(",
        "prefilter_decision",
        "participation_gate =",
        "expansion_gate =",
    )
    for token in forbidden:
        assert token not in source
    assert "ordered_maturation_records" in source
    assert "opportunity_state(record)" in source

"""Phase 65: GS455 maturation-state meaning belongs to Thesis / State."""

from pathlib import Path
from types import SimpleNamespace

from mide import gs310_unified_opportunity_state as unified
from mide import gs455_early_ignition_3m_confirmation as gs455
from mide.authorities import thesis_state


ROOT = Path(__file__).resolve().parents[1]


def _base(state=unified.DEVELOPING):
    return {
        "state": state,
        "color": unified.STATE_COLORS[state],
        "reason": "base",
        "next_step": "base next",
        "attention_provenance": [],
    }


def test_phase65_near_vwap_progression_maps_to_look_now(monkeypatch):
    monkeypatch.setattr(
        gs455,
        "progression_signal",
        lambda _record: {
            "active": True,
            "new_rung": "3m",
            "sequence": "30s -> 1m -> 3m",
            "vwap_distance_pct": 3.0,
        },
    )
    monkeypatch.setattr(
        gs455,
        "crossover_progression",
        lambda _record: {"stage": "CONFIRMATION"},
    )

    view = gs455._state_with_progression(
        lambda _record: _base(),
        {},
    )
    assert view["state"] == unified.LOOK_NOW
    assert "maturation reached 3M" in view["reason"]
    assert gs455._PROGRESSION_PROVENANCE in view["attention_provenance"]


def test_phase65_extended_progression_preserves_chase_wait(monkeypatch):
    monkeypatch.setattr(
        gs455,
        "progression_signal",
        lambda _record: {
            "active": True,
            "new_rung": "5m",
            "sequence": "30s -> 1m -> 3m -> 5m",
            "vwap_distance_pct": 6.0,
        },
    )
    monkeypatch.setattr(
        gs455,
        "crossover_progression",
        lambda _record: {"stage": "PERSISTENCE"},
    )

    view = gs455._state_with_progression(
        lambda _record: _base(unified.CHASE_WAIT),
        {},
    )
    assert view["state"] == unified.CHASE_WAIT
    assert "DO NOT CHASE" in view["next_step"]


def test_phase65_entry_and_halt_states_are_never_overridden(monkeypatch):
    monkeypatch.setattr(
        gs455,
        "progression_signal",
        lambda _record: {
            "active": True,
            "new_rung": "3m",
            "sequence": "30s -> 1m -> 3m",
            "vwap_distance_pct": 1.0,
        },
    )

    entry = gs455._state_with_progression(
        lambda _record: _base(unified.WATCH_FOR_ENTRY),
        {},
    )
    halted = gs455._state_with_progression(
        lambda _record: _base(unified.HALTED),
        {},
    )
    assert entry["state"] == unified.WATCH_FOR_ENTRY
    assert halted["state"] == unified.HALTED


def test_phase65_stale_thesis_generation_leaves_state_unchanged(monkeypatch):
    monkeypatch.setattr(
        gs455,
        "_thesis_state",
        lambda: SimpleNamespace(),
    )
    base = _base()
    assert gs455._state_with_progression(
        lambda _record: dict(base),
        {},
    ) == base
    assert gs455._install_state() is None


def test_phase65_state_meaning_lives_in_thesis_authority():
    legacy = (
        ROOT / "mide/gs455_early_ignition_3m_confirmation.py"
    ).read_text(encoding="utf-8")
    authority = (
        ROOT / "mide/authorities/thesis_state.py"
    ).read_text(encoding="utf-8")

    assert "def progression_opportunity_state(" in authority
    assert "def install_progression_state(" in authority
    assert "def _thesis_state(" in legacy

    start = legacy.index("def _state_with_progression(")
    end = legacy.index("def _progression_change(", start)
    facade = legacy[start:end]
    assert "progression_opportunity_state" in facade
    assert 'view["state"] = unified.LOOK_NOW' not in facade


def test_phase65_install_preserves_historical_wrapper_marker(monkeypatch):
    monkeypatch.setattr(
        unified,
        "opportunity_state",
        lambda record: _base(),
    )
    gs455._install_state()

    assert getattr(
        unified.opportunity_state,
        "_gs455_crossover_progression",
        False,
    )


def test_phase65_scope_is_thesis_only():
    source = (
        ROOT / "mide/authorities/thesis_state.py"
    ).read_text(encoding="utf-8")
    start = source.index("# GS455 ordered maturation Thesis / State interpretation")
    end = source.index('_LEADER_RESET_PROVENANCE =', start)
    block = source[start:end]

    forbidden = (
        "qualified_for_entry =",
        "qualified_for_alert =",
        "qualified_for_watch =",
        "place_order(",
        "submit_order(",
        "play_alert(",
        ".get_bars(",
        ".history(",
    )
    assert not any(token in block for token in forbidden)

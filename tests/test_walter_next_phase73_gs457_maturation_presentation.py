"""Phase 73: GS457 maturation attention belongs to Presentation + Audio."""

from pathlib import Path
from types import SimpleNamespace

from mide import gs310_unified_opportunity_state as unified
from mide import gs455_early_ignition_3m_confirmation as gs455
from mide import gs457_maturation_leader_priority as gs457
from mide.authorities import presentation_audio


ROOT = Path(__file__).resolve().parents[1]


def _progression():
    return {
        "active_rungs": ["1m", "3m"],
        "events": {
            "1m": {
                "crossed": True,
                "current_confirmed": True,
                "recent": True,
                "age_seconds": 60.0,
            },
            "3m": {
                "crossed": True,
                "current_confirmed": True,
                "recent": True,
                "age_seconds": 61.0,
            },
        },
        "ordered": True,
        "latest_new_rung": None,
        "stage": "CONFIRMATION",
        "sequence": "1m -> 3m",
    }


def test_phase73_authority_preserves_recent_confirmation_semantics(monkeypatch):
    monkeypatch.setattr(
        unified,
        "opportunity_state",
        lambda _record: {"state": unified.CHASE_WAIT},
    )
    monkeypatch.setattr(
        gs455,
        "crossover_progression",
        lambda _record: _progression(),
    )
    monkeypatch.setattr(
        gs455,
        "progression_signal",
        lambda _record: {"active": False, "new_rung": None},
    )
    monkeypatch.setattr(
        gs455,
        "_supporting_flow",
        lambda _record: True,
    )

    detail = presentation_audio.maturation_attention({"symbol": "RETO"})
    assert detail["fresh_maturation"] is False
    assert detail["sustained_confirmation"] is True
    assert detail["reason"] == "recent_3m_plus_confirmation"
    assert detail["band"] == presentation_audio.MATURATION_RECENT_CONFIRMATION_BAND


def test_phase73_gs457_public_name_delegates_lazily(monkeypatch):
    sentinel = {
        "band": 45,
        "reason": "sentinel",
        "fresh_maturation": True,
    }
    monkeypatch.setattr(
        presentation_audio,
        "maturation_attention",
        lambda _record: dict(sentinel),
    )
    assert gs457.maturation_attention({}) == sentinel


def test_phase73_presentation_internal_consumers_preserve_compatibility_seam():
    source = (
        ROOT / "mide/authorities/presentation_audio.py"
    ).read_text(encoding="utf-8")
    assert "def _maturation_attention_compat(" in source
    assert source.count("_maturation_attention_compat(record)") >= 3
    assert "_walter_next_presentation_facade" in source


def test_phase73_stale_presentation_generation_keeps_warm_fallback(monkeypatch):
    monkeypatch.setattr(
        gs457,
        "_presentation_audio",
        lambda: SimpleNamespace(),
    )
    monkeypatch.setattr(
        unified,
        "opportunity_state",
        lambda _record: {"state": unified.LOOK_NOW},
    )
    monkeypatch.setattr(
        gs455,
        "crossover_progression",
        lambda _record: {
            "active_rungs": [],
            "events": {},
            "ordered": True,
            "latest_new_rung": None,
            "stage": "NONE",
            "sequence": "",
        },
    )
    monkeypatch.setattr(
        gs455,
        "progression_signal",
        lambda _record: {"active": False, "new_rung": None},
    )
    monkeypatch.setattr(
        gs455,
        "_supporting_flow",
        lambda _record: False,
    )
    detail = gs457.maturation_attention({})
    assert detail["reason"] == "look_now"
    assert detail["band"] == gs457.LOOK_NOW_BAND


def test_phase73_scope_is_presentation_only():
    source = (
        ROOT / "mide/authorities/presentation_audio.py"
    ).read_text(encoding="utf-8")
    start = source.index("# GS457 maturation-leader presentation semantics")
    end = source.index("# Authoritative operator ordering", start)
    block = source[start:end]

    forbidden = (
        "qualified_for_entry =",
        "qualified_for_alert =",
        "qualified_for_watch =",
        "place_order(",
        "submit_order(",
        "prefilter_decision",
        ".get_bars(",
        ".history(",
    )
    assert not any(token in block for token in forbidden)

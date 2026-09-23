"""Phase 14 ownership contract for base extreme-mover presentation."""

from pathlib import Path

from mide import gs333_extreme_mover_operator_priority as gs333
from mide.authorities import presentation_audio


def test_gs333_base_behavior_delegates_to_presentation_audio():
    record = {
        "symbol": "TEST",
        "pct_change": 10.0,
        "discovery_reasons": [],
    }
    assert (
        gs333.extreme_market_event(record)
        == presentation_audio.base_extreme_market_event(record)
    )
    assert gs333.EXTREME_MOVER_PCT == presentation_audio.EXTREME_MOVER_PCT


def test_authority_selector_resolves_current_gs333_event_callable(monkeypatch):
    first = {"symbol": "AAA", "dollar_volume": 1_000_000}
    second = {"symbol": "BBB", "dollar_volume": 2_000_000}

    def installed_event(record):
        return {
            "symbol": record["symbol"],
            "pct_change": 90.0 if record["symbol"] == "AAA" else 100.0,
            "halted": False,
            "label": "EXTREME MOVER · WATCH",
        }

    monkeypatch.setattr(gs333, "extreme_market_event", installed_event)

    record, event = presentation_audio.prioritized_extreme_event([first, second])
    assert record is second
    assert event["symbol"] == "BBB"


def test_base_extreme_presentation_meaning_lives_in_authority():
    authority = Path("mide/authorities/presentation_audio.py").read_text(
        encoding="utf-8"
    )
    facade = Path("mide/gs333_extreme_mover_operator_priority.py").read_text(
        encoding="utf-8"
    )

    for name in (
        "base_extreme_market_event",
        "prioritized_extreme_event",
        "extreme_event_markup",
        "install_base_extreme_presentation",
    ):
        assert f"def {name}(" in authority

    assert "Compatibility facade" in facade
    assert "def _headline(" not in facade
    assert "def _halted(" not in facade
    assert "def _in_streamlit_run(" not in facade


def test_base_extreme_authority_remains_presentation_only():
    authority = Path("mide/authorities/presentation_audio.py").read_text(
        encoding="utf-8"
    )
    source = authority.split(
        "# Base extraordinary-mover presentation", 1
    )[1].split(
        "# Authoritative extreme-mover presentation semantics", 1
    )[0]

    forbidden = (
        "qualified_for_entry =",
        "qualified_for_alert =",
        "qualified_for_watch =",
        "place_order(",
        "submit_order(",
        "execute_order(",
        ".get_bars(",
        ".history(",
    )
    assert not any(token in source for token in forbidden)

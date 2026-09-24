"""GS543: fresh ignition/confirmation audio outranks persistence chatter."""

from pathlib import Path

from mide import gs455_early_ignition_3m_confirmation as gs455
from mide.authorities import presentation_audio


ROOT = Path(__file__).resolve().parents[1]


def _signal(rung: str, stage: str, *, distance: float = 1.0) -> dict:
    return {
        "active": True,
        "new_rung": rung,
        "stage": stage,
        "vwap_distance_pct": distance,
    }


def test_gs543_fresh_1m_ignition_beats_5m_persistence(monkeypatch):
    signals = {
        "DDC": _signal("5m", "PERSISTENCE"),
        "RAVE": _signal("1m", "IGNITION"),
    }
    monkeypatch.setattr(
        gs455,
        "progression_signal",
        lambda record: signals[record["symbol"]],
    )

    phrase = presentation_audio.progression_audio_phrase(
        [{"symbol": "DDC"}, {"symbol": "RAVE"}]
    )

    assert phrase.startswith("RAVE. LOOK NOW.")
    assert "1 minute" in phrase
    assert "DDC" not in phrase


def test_gs543_3m_confirmation_beats_fresh_1m_ignition(monkeypatch):
    signals = {
        "IGN": _signal("1m", "IGNITION"),
        "CONF": _signal("3m", "CONFIRMATION"),
    }
    monkeypatch.setattr(
        gs455,
        "progression_signal",
        lambda record: signals[record["symbol"]],
    )

    phrase = presentation_audio.progression_audio_phrase(
        [{"symbol": "IGN"}, {"symbol": "CONF"}]
    )

    assert phrase.startswith("CONF. LOOK NOW.")
    assert "3 minute" in phrase


def test_gs543_persistence_still_speaks_when_no_earlier_stage_competes(monkeypatch):
    signals = {
        "TEN": _signal("10m", "PERSISTENCE"),
        "FIVE": _signal("5m", "PERSISTENCE"),
    }
    monkeypatch.setattr(
        gs455,
        "progression_signal",
        lambda record: signals[record["symbol"]],
    )

    phrase = presentation_audio.progression_audio_phrase(
        [{"symbol": "TEN"}, {"symbol": "FIVE"}]
    )

    assert phrase.startswith("FIVE. LOOK NOW.")
    assert "5 minute" in phrase


def test_gs543_extended_selected_event_keeps_anti_chase_language(monkeypatch):
    monkeypatch.setattr(
        gs455,
        "progression_signal",
        lambda _record: _signal("1m", "IGNITION", distance=8.0),
    )

    phrase = presentation_audio.progression_audio_phrase(
        [{"symbol": "RAVE"}]
    )

    assert "Extended. Do not chase." in phrase


def test_gs543_priority_contract_matches_operator_ladder():
    priority = presentation_audio.progression_audio_priority

    assert priority(_signal("3m", "CONFIRMATION")) > priority(
        _signal("1m", "IGNITION")
    )
    assert priority(_signal("1m", "IGNITION")) > priority(
        _signal("5m", "PERSISTENCE")
    )
    assert priority(_signal("1m", "IGNITION")) > priority(
        _signal("30s", "IGNITION")
    )
    assert priority(_signal("5m", "PERSISTENCE")) > priority(
        _signal("10m", "PERSISTENCE")
    )


def test_gs543_scope_is_audio_selection_only():
    source = (
        ROOT / "mide/authorities/presentation_audio.py"
    ).read_text(encoding="utf-8")
    start = source.index("def progression_audio_priority(")
    end = source.index("def install_progression_alert_priority(", start)
    block = source[start:end]

    forbidden = (
        "qualified_for_entry =",
        "qualified_for_alert =",
        "qualified_for_watch =",
        "mission_rank =",
        "participation_score =",
        "expansion_score =",
        "opportunity_state =",
        "place_order(",
        "submit_order(",
        ".get_bars(",
        ".history(",
    )
    assert not any(token in block for token in forbidden)

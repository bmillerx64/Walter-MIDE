"""Phase 66: GS455 maturation alert semantics belong to Presentation + Audio."""

from pathlib import Path
from types import SimpleNamespace

from mide import escalation
from mide import gs455_early_ignition_3m_confirmation as gs455
from mide.authorities import presentation_audio


ROOT = Path(__file__).resolve().parents[1]


def test_phase66_spoken_rung_mapping_is_preserved():
    assert gs455._spoken_rung("30s") == "30 second"
    assert gs455._spoken_rung("1m") == "1 minute"
    assert gs455._spoken_rung("3m") == "3 minute"
    assert gs455._spoken_rung("15m") == "15 minute"


def test_phase66_progression_change_uses_authoritative_signal(monkeypatch):
    monkeypatch.setattr(
        gs455,
        "progression_signal",
        lambda _record: {
            "active": True,
            "new_rung": "3m",
            "timestamp": "2026-09-15T10:39:00-04:00",
        },
    )
    assert gs455._progression_change(
        {"symbol": "RETO"}
    ) == {
        "symbol": "RETO",
        "from": "3M CROSS@2026-09-15T10:39:00-04:00",
        "to": "ST/VWAP MATURATION 3M",
    }


def test_phase66_progression_phrase_preserves_anti_chase(monkeypatch):
    monkeypatch.setattr(
        gs455,
        "progression_signal",
        lambda record: {
            "active": True,
            "new_rung": record["rung"],
            "stage": "PERSISTENCE",
            "vwap_distance_pct": 6.0,
        },
    )
    phrase = gs455._progression_phrase(
        [
            {
                "symbol": "RETO",
                "rung": "5m",
            }
        ]
    )
    assert "LOOK NOW" in phrase
    assert "5 minute" in phrase
    assert "Do not chase" in phrase


def test_phase66_stale_presentation_generation_fails_closed(monkeypatch):
    monkeypatch.setattr(
        gs455,
        "_presentation_audio",
        lambda: SimpleNamespace(),
    )
    assert gs455._progression_change(
        {"symbol": "TEST"}
    ) is None
    assert gs455._spoken_rung("3m") == "3m"
    assert gs455._progression_phrase(
        [{"symbol": "TEST"}]
    ) == ""
    assert gs455._install_alert_priority() is None


def test_phase66_alert_meaning_lives_in_presentation_audio():
    legacy = (
        ROOT / "mide/gs455_early_ignition_3m_confirmation.py"
    ).read_text(encoding="utf-8")
    authority = (
        ROOT / "mide/authorities/presentation_audio.py"
    ).read_text(encoding="utf-8")

    for name in (
        "progression_change",
        "spoken_progression_rung",
        "progression_audio_phrase",
        "install_progression_alert_priority",
    ):
        assert f"def {name}(" in authority

    start = legacy.index("def _presentation_audio(")
    end = legacy.index("def _inherit(", start)
    facade = legacy[start:end]
    assert "def _presentation_audio(" in facade
    assert "ST/VWAP MATURATION" not in facade
    assert "semantic_chime_count" not in facade


def test_phase66_installer_preserves_historical_wrapper_markers(monkeypatch):
    def base_changes(records):
        return []

    def base_phrase(records):
        return ""

    monkeypatch.setattr(
        escalation,
        "escalation_state_changes",
        base_changes,
    )
    monkeypatch.setattr(
        escalation,
        "escalation_alert_phrase",
        base_phrase,
    )

    gs455._install_alert_priority()

    assert getattr(
        escalation.escalation_state_changes,
        "_gs455_crossover_progression",
        False,
    )
    assert getattr(
        escalation.escalation_alert_phrase,
        "_gs455_crossover_progression",
        False,
    )


def test_phase66_scope_is_presentation_audio_only():
    source = (
        ROOT / "mide/authorities/presentation_audio.py"
    ).read_text(encoding="utf-8")
    start = source.index("# GS455 ordered maturation presentation / audio")
    end = source.index("# GS460/GS461 ST compression", start)
    block = source[start:end]

    forbidden = (
        "qualified_for_entry =",
        "qualified_for_alert =",
        "qualified_for_watch =",
        "candidate_status =",
        "place_order(",
        "submit_order(",
        ".get_bars(",
        ".history(",
    )
    assert not any(token in block for token in forbidden)

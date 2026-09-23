"""Phase 11 ownership contract for runner-maturation audio."""

from pathlib import Path

from mide import gs492_maturation_transition_audio as gs492
from mide import gs512_audio_architecture_gate_bridge as gs512
from mide.authorities import presentation_audio


def test_gs492_delegates_to_presentation_audio():
    record = {
        "symbol": "TEST",
        "status": "PASS",
        "candidate_status": "Watching",
        "participation_gate": {"passed": False},
        "structure_gate": {"passed": False},
        "timeframes": {},
    }
    assert gs492.maturation_transition(record) == presentation_audio.maturation_transition(record)
    assert gs492.maturation_audio_phrase([record]) == presentation_audio.maturation_audio_phrase([record])


def test_gs512_delegates_gate_truth_to_presentation_audio():
    record = {"participation_gate": {"passed": True}}
    assert (
        gs512.authoritative_gate_passed(record, "participation_gate")
        is presentation_audio.authoritative_gate_passed(record, "participation_gate")
    )


def test_audio_meaning_lives_in_presentation_audio():
    authority = Path("mide/authorities/presentation_audio.py").read_text(encoding="utf-8")
    gs492_source = Path("mide/gs492_maturation_transition_audio.py").read_text(encoding="utf-8")
    gs512_source = Path("mide/gs512_audio_architecture_gate_bridge.py").read_text(encoding="utf-8")

    assert "def maturation_transition(" in authority
    assert "def maturation_audio_phrase(" in authority
    assert "def authoritative_gate_passed(" in authority
    assert "def install_maturation_transition_audio(" in authority
    assert "def install_audio_architecture_gate_bridge(" in authority

    assert "Compatibility facade" in gs492_source
    assert "Compatibility facade" in gs512_source

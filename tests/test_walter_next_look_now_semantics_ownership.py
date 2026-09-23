"""Phase 6 ownership contract for LOOK NOW semantic adjudication."""

from pathlib import Path

from mide.authorities import thesis_state
from mide import gs467_look_now_semantic_consolidation as gs467


def test_gs467_is_a_compatibility_shim_to_thesis_state():
    assert gs467.legacy_1m_ignition_look_now is thesis_state.legacy_1m_ignition_look_now
    assert gs467.bottom_up_urgency is thesis_state.bottom_up_urgency
    assert gs467.consolidated_look_now is thesis_state.consolidated_look_now
    assert gs467.install is thesis_state.install_look_now_semantics


def test_look_now_semantic_meaning_lives_in_thesis_state():
    authority = Path("mide/authorities/thesis_state.py").read_text(encoding="utf-8")
    legacy = Path("mide/gs467_look_now_semantic_consolidation.py").read_text(encoding="utf-8")

    assert "def legacy_1m_ignition_look_now(" in authority
    assert "def bottom_up_urgency(" in authority
    assert "def consolidated_look_now(" in authority
    assert "def install_look_now_semantics(" in authority

    assert "def legacy_1m_ignition_look_now(" not in legacy
    assert "def bottom_up_urgency(" not in legacy
    assert "def consolidated_look_now(" not in legacy
    assert "def install(" not in legacy

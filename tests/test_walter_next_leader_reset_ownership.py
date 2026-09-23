"""Phase 9 ownership contract for proven-leader reset/re-ignition."""

from pathlib import Path

from mide import gs477_leader_reset_reignition as gs477
from mide.authorities import market_evidence, presentation_audio, thesis_state


def test_gs477_constants_resolve_from_market_evidence():
    assert gs477.LEADER_MEMORY_TTL_SECONDS == market_evidence.LEADER_MEMORY_TTL_SECONDS
    assert gs477.RESET_WATCH == market_evidence.RESET_WATCH
    assert gs477.REIGNITION == market_evidence.REIGNITION
    assert gs477.THREE_MINUTE_CONFIRMATION == market_evidence.THREE_MINUTE_CONFIRMATION


def test_leader_reset_responsibilities_have_authoritative_homes():
    market = Path("mide/authorities/market_evidence.py").read_text(encoding="utf-8")
    thesis = Path("mide/authorities/thesis_state.py").read_text(encoding="utf-8")
    presentation = Path("mide/authorities/presentation_audio.py").read_text(encoding="utf-8")
    legacy = Path("mide/gs477_leader_reset_reignition.py").read_text(encoding="utf-8")

    assert "class LeaderMemory" in market
    assert "def leader_reset_evidence(" in market
    assert "def apply_leader_reset_marks(" in market
    assert "def leader_reset_opportunity_state(" in thesis
    assert "def augment_leader_reset_records(" in presentation
    assert "def enrich_visible_records(" in presentation
    assert "def leader_reset_audio_phrase(" in presentation
    assert "Compatibility facade" in legacy


def test_presentation_authority_does_not_freeze_ui_callable_imports():
    source = Path("mide/authorities/presentation_audio.py").read_text(encoding="utf-8")
    assert "from mide.ui import" not in source
    assert 'getattr(ui, name)' in source

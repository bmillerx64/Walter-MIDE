"""Phase 16 ownership contract for market-leader continuity."""

from pathlib import Path

from mide import gs443_market_leader_radar_continuity as gs443
from mide.authorities import presentation_audio


def test_gs443_delegates_to_presentation_audio():
    records = []
    assert (
        gs443.market_leader_candidate(records, mission={})
        == presentation_audio.market_leader_candidate(records, mission={})
    )
    assert gs443.MAJOR_MOVER_PCT == presentation_audio.MAJOR_MOVER_PCT == 20.0
    assert (
        gs443.MIN_DOLLAR_VOLUME
        == presentation_audio.MIN_DOLLAR_VOLUME
        == 250_000.0
    )
    assert gs443.LEADER_DOMINANCE == presentation_audio.LEADER_DOMINANCE == 78.0


def test_market_leader_meaning_lives_in_presentation_audio():
    authority = Path("mide/authorities/presentation_audio.py").read_text(
        encoding="utf-8"
    )
    facade = Path("mide/gs443_market_leader_radar_continuity.py").read_text(
        encoding="utf-8"
    )

    for name in (
        "market_leader_candidate",
        "market_leader_markup",
        "install_market_leader_continuity",
    ):
        assert f"def {name}(" in authority

    assert "Compatibility facade" in facade
    assert "def _focused_symbols(" not in facade
    assert "def _in_streamlit_run(" not in facade


def test_market_leader_authority_is_watch_only():
    authority = Path("mide/authorities/presentation_audio.py").read_text(
        encoding="utf-8"
    )
    source = authority.split(
        "# Market-leader continuity presentation", 1
    )[1].split(
        "# Authoritative extreme-mover presentation semantics", 1
    )[0]

    forbidden = (
        "qualified_for_entry =",
        "qualified_for_alert =",
        "participation_score =",
        "expansion_score =",
        "opportunity_state =",
        "candidate_status =",
        "attention_score =",
        "market_dominance_score =",
        "play_alert(",
        "request_scan(",
        "place_order(",
    )
    assert not any(token in source for token in forbidden)

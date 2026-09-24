"""Phase 25: GS414/GS436 final render ownership belongs to Presentation + Audio."""

from pathlib import Path

from mide import gs414_final_enriched_opportunity_order as gs414
from mide.authorities import presentation_audio


ROOT = Path(__file__).resolve().parents[1]


def test_gs414_record_collection_delegates_to_presentation_audio(monkeypatch):
    sentinel = [{"symbol": "AUTH"}]

    monkeypatch.setattr(
        presentation_audio,
        "final_enriched_opportunity_records",
        lambda records, actionable_function=None: sentinel,
    )

    assert gs414.final_enriched_opportunity_records([{"symbol": "LEGACY"}]) is sentinel


def test_final_owner_sentinel_is_authoritative_presentation_contract():
    assert gs414.FINAL_ORDER_OWNER_ATTR == presentation_audio.FINAL_ORDER_OWNER_ATTR
    assert not gs414.FINAL_ORDER_OWNER_ATTR.startswith("_gs")


def test_gs414_keeps_historical_late_installer_sequence_as_coordinator():
    source = (ROOT / "mide/gs414_final_enriched_opportunity_order.py").read_text(
        encoding="utf-8"
    )
    body = source.split("def install() -> None:", 1)[1]

    ordered = (
        "_install_gs475()",
        "_install_gs464()",
        "_install_gs462()",
        "_install_gs463()",
        "_install_gs465()",
        "_install_gs466()",
        "_install_gs467()",
        "_install_gs468()",
        "_install_gs474()",
        "_install_gs477()",
        "_install_gs492()",
        "_install_gs512()",
        "_install_gs493()",
        "_install_gs495()",
        "_install_gs497()",
        "_install_gs517()",
        "_install_gs525()",
        "_install_gs526()",
        "_install_gs527()",
        "_install_gs528()",
        "_install_gs539()",
    )
    positions = [body.index(token) for token in ordered]
    assert positions == sorted(positions)


def test_gs414_source_no_longer_duplicates_final_collection_or_render_freeze():
    source = (ROOT / "mide/gs414_final_enriched_opportunity_order.py").read_text(
        encoding="utf-8"
    )

    assert "from mide.authorities import presentation_audio as _presentation" in source
    assert "ordered_escalation_records(enriched)" not in source
    assert "def render_with_final_enriched_order(" not in source
    assert "_presentation.bind_final_enriched_opportunity_order(" in source


def test_phase25_final_render_boundary_remains_presentation_only():
    source = (ROOT / "mide/gs414_final_enriched_opportunity_order.py").read_text(
        encoding="utf-8"
    )
    forbidden = (
        "qualified_for_entry =",
        "qualified_for_alert =",
        "qualified_for_watch =",
        "mission_rank =",
        "participation_score =",
        "opportunity_score =",
        "place_order(",
        "submit_order(",
        "requests.get(",
        "requests.post(",
    )
    assert not any(token in source for token in forbidden)

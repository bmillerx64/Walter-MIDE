"""Phase 13 ownership contract for extreme-mover presentation semantics."""

from pathlib import Path

from mide import gs333_extreme_mover_operator_priority as gs333
from mide import gs465_presentation_priority_cleanup as gs465
from mide import gs466_extreme_awareness_continuity as gs466
from mide import gs495_extreme_attention_anti_chase_semantics as gs495
from mide.authorities import presentation_audio


def test_cleanup_and_anti_chase_share_one_extreme_event_wrapper(monkeypatch):
    def baseline(record):
        return {
            "symbol": record.get("symbol", "TEST"),
            "label": "EXTREME MOVER · LOOK NOW",
            "guidance": "legacy",
            "vwap_distance_pct": 4.4,
            "halted": False,
        }

    monkeypatch.setattr(gs333, "extreme_market_event", baseline)

    presentation_audio.activate_extreme_event_stage("cleanup")
    first = gs333.extreme_market_event
    presentation_audio.activate_extreme_event_stage("anti_chase")
    second = gs333.extreme_market_event

    assert first is second
    assert first is not baseline
    assert getattr(first, "_walter_next_extreme_event_semantics_owner", False)
    assert getattr(first, "_walter_next_extreme_event_stages", set()) == {
        "cleanup",
        "anti_chase",
    }


def test_historical_install_points_activate_the_authoritative_extreme_stages(monkeypatch):
    activated = []
    awareness = []

    monkeypatch.setattr(
        presentation_audio,
        "activate_extreme_event_stage",
        lambda stage: activated.append(stage),
    )
    monkeypatch.setattr(
        presentation_audio,
        "install_extreme_selection_continuity",
        lambda: None,
    )
    monkeypatch.setattr(
        presentation_audio,
        "install_extreme_awareness_continuity",
        lambda: awareness.append("awareness"),
    )

    gs465._install_extreme_semantics()
    gs466.install()
    gs495.install()

    assert activated == ["cleanup", "anti_chase"]
    assert awareness == ["awareness"]


def test_extreme_semantic_meaning_lives_in_presentation_audio():
    authority = Path("mide/authorities/presentation_audio.py").read_text(encoding="utf-8")

    for name in (
        "cleaned_extreme_event",
        "truthful_extreme_market_event",
        "activate_extreme_event_stage",
        "prioritized_extreme_with_watch_continuity",
        "install_extreme_selection_continuity",
        "extreme_awareness_continuity",
        "install_extreme_awareness_continuity",
    ):
        assert f"def {name}(" in authority

    assert "Compatibility facade" in Path(
        "mide/gs466_extreme_awareness_continuity.py"
    ).read_text(encoding="utf-8")
    assert "Compatibility facade" in Path(
        "mide/gs495_extreme_attention_anti_chase_semantics.py"
    ).read_text(encoding="utf-8")


def test_gs465_keeps_ordering_facade_but_extreme_helpers_delegate():
    source = Path("mide/gs465_presentation_priority_cleanup.py").read_text(
        encoding="utf-8"
    )
    assert 'activate_extreme_event_stage("cleanup")' in source
    assert "install_extreme_selection_continuity()" in source

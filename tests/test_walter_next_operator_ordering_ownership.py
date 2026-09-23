"""Phase 12 contract: one authoritative operator sorter, staged legacy activation."""

from __future__ import annotations

from pathlib import Path

from mide import gs369_escalation_priority_order as gs369
from mide import gs463_state_first_operator_order as gs463
from mide import gs465_presentation_priority_cleanup as gs465
from mide import gs497_rank_aware_attention_order as gs497
from mide import gs517_fresh_event_priority as gs517
from mide import gs539_pe_strength_order as gs539
from mide.authorities import presentation_audio


EXPECTED_STAGES = {
    "state_first",
    "state_contiguous",
    "rank_aware",
    "fresh_event",
    "pe_strength",
}


def test_authoritative_sorter_keeps_one_callable_identity_across_all_stages(monkeypatch):
    def baseline(records):
        return list(records)

    monkeypatch.setattr(gs369, "ordered_escalation_records", baseline)

    first = None
    for stage in (
        "state_first",
        "state_contiguous",
        "rank_aware",
        "fresh_event",
        "pe_strength",
    ):
        presentation_audio.activate_operator_order_stage(stage)
        current = gs369.ordered_escalation_records
        if first is None:
            first = current
            assert first is not baseline
        else:
            assert current is first

    assert getattr(first, "_walter_next_authoritative_operator_order_owner", False)
    assert getattr(first, "_walter_next_operator_order_stages", set()) == EXPECTED_STAGES


def test_historical_install_points_map_to_the_authoritative_stages(monkeypatch):
    activated = []

    monkeypatch.setattr(
        presentation_audio,
        "activate_operator_order_stage",
        lambda stage: activated.append(stage),
    )
    monkeypatch.setattr(presentation_audio, "install_pe_strength_state", lambda: None)

    gs463.install()
    gs465._install_order()
    gs497.install()
    gs517.install()
    gs539.install()

    assert activated == [
        "state_first",
        "state_contiguous",
        "rank_aware",
        "fresh_event",
        "pe_strength",
    ]


def test_ordering_meaning_no_longer_lives_in_numbered_modules():
    authority = Path("mide/authorities/presentation_audio.py").read_text(encoding="utf-8")

    for name in (
        "effective_operator_attention_band",
        "ordered_state_contiguous_records",
        "current_mission_rank",
        "ordered_rank_aware_records",
        "fresh_maturation_event",
        "ordered_fresh_event_records",
        "pe_strength_score",
        "ordered_pe_strength_records",
        "activate_operator_order_stage",
    ):
        assert f"def {name}(" in authority

    for path in (
        "mide/gs463_state_first_operator_order.py",
        "mide/gs497_rank_aware_attention_order.py",
        "mide/gs517_fresh_event_priority.py",
        "mide/gs539_pe_strength_order.py",
    ):
        source = Path(path).read_text(encoding="utf-8")
        assert "Compatibility facade" in source


def test_gs465_keeps_extreme_semantics_but_delegates_ordering():
    source = Path("mide/gs465_presentation_priority_cleanup.py").read_text(
        encoding="utf-8"
    )
    assert '_presentation.activate_operator_order_stage("state_contiguous")' in source
    assert "def cleaned_extreme_event(" in source
    assert "def prioritized_extreme_with_watch_continuity(" in source

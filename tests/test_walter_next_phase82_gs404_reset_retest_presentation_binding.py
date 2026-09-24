"""Phase 82: GS404 presentation binding belongs to Presentation + Audio."""

from pathlib import Path
from types import SimpleNamespace

from mide import gs404_reset_retest_look_now as gs404
from mide import ui
from mide.authorities import presentation_audio


ROOT = Path(__file__).resolve().parents[1]


def test_phase82_authority_installs_actionable_wrapper(monkeypatch):
    def baseline(records):
        return list(records)

    monkeypatch.setattr(
        ui,
        "actionable_candidate_records",
        baseline,
    )
    monkeypatch.setattr(
        presentation_audio,
        "augment_reset_retest_visible_records",
        lambda records, visible: list(visible),
    )

    presentation_audio.install_reset_retest_awareness()
    installed = ui.actionable_candidate_records

    assert installed is not baseline
    assert getattr(
        installed,
        "_gs404_reset_retest",
        False,
    ) is True
    assert getattr(
        installed,
        "_gs404_original",
        None,
    ) is baseline

    presentation_audio.install_reset_retest_awareness()
    assert ui.actionable_candidate_records is installed


def test_phase82_legacy_install_delegates_to_both_authorities(monkeypatch):
    calls = []
    monkeypatch.setattr(
        gs404,
        "_presentation_audio",
        lambda: SimpleNamespace(
            install_reset_retest_awareness=lambda: calls.append("presentation")
        ),
    )
    monkeypatch.setattr(
        gs404,
        "_thesis_state",
        lambda: SimpleNamespace(
            install_reset_retest_state=lambda: calls.append("state")
        ),
    )

    gs404.install()
    assert calls == ["presentation", "state"]


def test_phase82_stale_presentation_generation_preserves_ui_fallback(monkeypatch):
    monkeypatch.setattr(
        gs404,
        "_presentation_audio",
        lambda: SimpleNamespace(),
    )
    monkeypatch.setattr(
        gs404,
        "_thesis_state",
        lambda: SimpleNamespace(
            install_reset_retest_state=lambda: None
        ),
    )

    def baseline(records):
        return list(records)

    monkeypatch.setattr(
        ui,
        "actionable_candidate_records",
        baseline,
    )

    gs404.install()
    installed = ui.actionable_candidate_records
    assert installed is not baseline
    assert getattr(
        installed,
        "_gs404_reset_retest",
        False,
    ) is True


def test_phase82_gs404_install_is_now_a_thin_split_authority_coordinator():
    legacy = (
        ROOT / "mide/gs404_reset_retest_look_now.py"
    ).read_text(encoding="utf-8")
    start = legacy.index("def install()")
    block = legacy[start:]

    assert '"install_reset_retest_awareness"' in block
    assert '"install_reset_retest_state"' in block


def test_phase82_presentation_binding_lives_in_presentation_audio():
    authority = (
        ROOT / "mide/authorities/presentation_audio.py"
    ).read_text(encoding="utf-8")
    assert "def install_reset_retest_awareness(" in authority


def test_phase82_scope_is_presentation_only():
    source = (
        ROOT / "mide/authorities/presentation_audio.py"
    ).read_text(encoding="utf-8")
    start = source.index("def install_reset_retest_awareness(")
    end = source.index("# GS401 final Opportunity render ordering", start)
    block = source[start:end]

    forbidden = (
        "opportunity_state =",
        "place_order(",
        "submit_order(",
        "request_scan(",
        ".get_bars(",
        ".history(",
    )
    assert not any(token in block for token in forbidden)

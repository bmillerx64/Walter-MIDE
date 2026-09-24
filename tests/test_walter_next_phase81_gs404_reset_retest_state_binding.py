"""Phase 81: GS404 reset/retest state binding belongs to Thesis / State."""

from pathlib import Path
from types import SimpleNamespace

from mide import gs310_unified_opportunity_state as unified
from mide import gs311_unified_voice as voice
from mide import gs314_state_consistency as consistency
from mide import gs363_operator_attention_hierarchy as hierarchy
from mide import gs404_reset_retest_look_now as gs404
from mide.authorities import thesis_state


ROOT = Path(__file__).resolve().parents[1]


def test_phase81_authority_installs_state_wrapper_and_aliases(monkeypatch):
    def baseline(record):
        return {
            "state": unified.DEVELOPING,
            "color": unified.STATE_COLORS[unified.DEVELOPING],
        }

    monkeypatch.setattr(
        unified,
        "opportunity_state",
        baseline,
    )
    monkeypatch.setattr(
        voice,
        "opportunity_state",
        baseline,
    )
    monkeypatch.setattr(
        consistency,
        "opportunity_state",
        baseline,
    )
    monkeypatch.setattr(
        hierarchy,
        "opportunity_state",
        baseline,
    )

    thesis_state.install_reset_retest_state()
    installed = unified.opportunity_state

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
    assert voice.opportunity_state is installed
    assert consistency.opportunity_state is installed
    assert hierarchy.opportunity_state is installed

    thesis_state.install_reset_retest_state()
    assert unified.opportunity_state is installed


def test_phase81_legacy_install_delegates_state_binding_lazily(monkeypatch):
    calls = []

    monkeypatch.setattr(
        gs404,
        "_thesis_state",
        lambda: SimpleNamespace(
            install_reset_retest_state=lambda: calls.append("state")
        ),
    )

    class UIStub:
        pass

    from mide import ui
    original_records = ui.actionable_candidate_records

    def already_bound(records):
        return original_records(records)

    already_bound._gs404_reset_retest = True
    monkeypatch.setattr(
        ui,
        "actionable_candidate_records",
        already_bound,
    )

    gs404.install()
    assert calls == ["state"]


def test_phase81_stale_thesis_generation_preserves_state_binding_fallback(monkeypatch):
    monkeypatch.setattr(
        gs404,
        "_thesis_state",
        lambda: SimpleNamespace(),
    )

    def baseline(record):
        return {
            "state": unified.DEVELOPING,
            "color": unified.STATE_COLORS[unified.DEVELOPING],
        }

    monkeypatch.setattr(
        unified,
        "opportunity_state",
        baseline,
    )
    monkeypatch.setattr(
        voice,
        "opportunity_state",
        baseline,
    )
    monkeypatch.setattr(
        consistency,
        "opportunity_state",
        baseline,
    )
    monkeypatch.setattr(
        hierarchy,
        "opportunity_state",
        baseline,
    )

    from mide import ui
    original_records = ui.actionable_candidate_records

    def already_bound(records):
        return original_records(records)

    already_bound._gs404_reset_retest = True
    monkeypatch.setattr(
        ui,
        "actionable_candidate_records",
        already_bound,
    )

    gs404.install()
    installed = unified.opportunity_state
    assert installed is not baseline
    assert getattr(installed, "_gs404_reset_retest", False) is True
    assert voice.opportunity_state is installed
    assert consistency.opportunity_state is installed
    assert hierarchy.opportunity_state is installed


def test_phase81_actionable_record_binding_remains_for_final_presentation_slice():
    legacy = (
        ROOT / "mide/gs404_reset_retest_look_now.py"
    ).read_text(encoding="utf-8")
    install_start = legacy.index("def install()")
    block = legacy[install_start:]
    assert "ui.actionable_candidate_records" in block
    assert "augment_reset_retest_records(" in block


def test_phase81_state_binding_lives_in_thesis_state():
    legacy = (
        ROOT / "mide/gs404_reset_retest_look_now.py"
    ).read_text(encoding="utf-8")
    authority = (
        ROOT / "mide/authorities/thesis_state.py"
    ).read_text(encoding="utf-8")

    assert "def install_reset_retest_state(" in authority
    assert '"install_reset_retest_state"' in legacy


def test_phase81_scope_is_state_only():
    source = (
        ROOT / "mide/authorities/thesis_state.py"
    ).read_text(encoding="utf-8")
    start = source.index("def install_reset_retest_state(")
    end = source.index('_LEADER_RESET_PROVENANCE =', start)
    block = source[start:end]

    forbidden = (
        "ui.actionable_candidate_records",
        "place_order(",
        "submit_order(",
        "request_scan(",
        ".get_bars(",
        ".history(",
    )
    assert not any(token in block for token in forbidden)

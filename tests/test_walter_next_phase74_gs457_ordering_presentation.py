"""Phase 74: GS457 ordering and GS369 bind belong to Presentation + Audio."""

from pathlib import Path
from types import SimpleNamespace

from mide import gs369_escalation_priority_order as gs369
from mide import gs457_maturation_leader_priority as gs457
from mide.authorities import presentation_audio


ROOT = Path(__file__).resolve().parents[1]


def test_phase74_effective_priority_semantics_are_preserved():
    assert presentation_audio.effective_maturation_priority(
        {
            "fresh_maturation": False,
            "sustained_confirmation": False,
            "rung_rank": 6,
            "freshness": -1.0,
        }
    ) == (0, float("-inf"))
    assert presentation_audio.effective_maturation_priority(
        {
            "fresh_maturation": True,
            "sustained_confirmation": False,
            "rung_rank": 3,
            "freshness": -61.0,
        }
    ) == (3, -61.0)


def test_phase74_legacy_order_name_delegates_lazily(monkeypatch):
    sentinel = [{"symbol": "AUTH"}]
    monkeypatch.setattr(
        presentation_audio,
        "ordered_maturation_records",
        lambda _records: list(sentinel),
    )
    assert gs457.ordered_maturation_records([]) == sentinel


def test_phase74_installer_preserves_historical_gs457_lineage(monkeypatch):
    def baseline(records):
        return list(records)

    monkeypatch.setattr(
        gs369,
        "ordered_escalation_records",
        baseline,
    )
    presentation_audio.install_maturation_leader_priority()
    installed = gs369.ordered_escalation_records

    assert installed is not baseline
    assert getattr(
        installed,
        "_gs457_maturation_leader_priority",
        False,
    ) is True
    assert getattr(
        installed,
        "_gs457_original",
        None,
    ) is baseline
    assert getattr(
        installed,
        presentation_audio.MATURATION_ORDER_OWNER,
        False,
    ) is True

    presentation_audio.install_maturation_leader_priority()
    assert gs369.ordered_escalation_records is installed


def test_phase74_stale_presentation_generation_preserves_install_fallback(monkeypatch):
    def baseline(records):
        return list(records)

    monkeypatch.setattr(
        gs457,
        "_presentation_audio",
        lambda: SimpleNamespace(),
    )
    monkeypatch.setattr(
        gs369,
        "ordered_escalation_records",
        baseline,
    )

    gs457.install()
    installed = gs369.ordered_escalation_records
    assert installed is not baseline
    assert getattr(
        installed,
        "_gs457_maturation_leader_priority",
        False,
    ) is True


def test_phase74_ordering_meaning_lives_in_presentation_audio():
    legacy = (
        ROOT / "mide/gs457_maturation_leader_priority.py"
    ).read_text(encoding="utf-8")
    authority = (
        ROOT / "mide/authorities/presentation_audio.py"
    ).read_text(encoding="utf-8")

    for name in (
        "effective_maturation_priority",
        "maturation_priority_sort_key",
        "ordered_maturation_records",
        "install_maturation_leader_priority",
    ):
        assert f"def {name}(" in authority

    assert '"ordered_maturation_records"' in legacy
    assert '"install_maturation_leader_priority"' in legacy


def test_phase74_scope_is_presentation_only():
    source = (
        ROOT / "mide/authorities/presentation_audio.py"
    ).read_text(encoding="utf-8")
    start = source.index("MATURATION_ORDER_OWNER")
    end = source.index("# Authoritative operator ordering", start)
    block = source[start:end]

    forbidden = (
        "qualified_for_entry =",
        "qualified_for_alert =",
        "qualified_for_watch =",
        "place_order(",
        "submit_order(",
        "prefilter_decision",
        ".get_bars(",
        ".history(",
    )
    assert not any(token in block for token in forbidden)

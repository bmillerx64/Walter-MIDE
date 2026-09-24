"""Phase 56: GS528 is a warm-deploy-safe lazy Entry Authority shim."""

from pathlib import Path
from types import SimpleNamespace

from mide import gs528_canonical_entry_ready as gs528
from mide.authorities import entry_authority


ROOT = Path(__file__).resolve().parents[1]


def test_phase56_current_runtime_preserves_exact_authority_identity():
    assert gs528.canonical_candidate_status is entry_authority.canonical_candidate_status
    assert gs528.entry_contract is entry_authority.entry_contract
    assert gs528.install is entry_authority.install
    assert gs528.state_with_entry_contract is entry_authority.state_with_entry_contract


def test_phase56_stale_entry_authority_fails_closed(monkeypatch):
    monkeypatch.setattr(gs528, "_entry_authority", lambda: SimpleNamespace())

    stale_ready = {
        "candidate_status": "Entry Ready",
        "qualified_for_entry": True,
    }
    assert gs528.canonical_candidate_status(stale_ready) == "Strengthening"

    contract = gs528.entry_contract(stale_ready)
    assert contract["qualified_for_entry"] is False
    assert contract["label"] == "SETTING UP"
    assert contract["legacy_false_entry_ready"] is True
    assert contract["authority"] == "STALE_ENTRY_AUTHORITY_FALLBACK"

    original = lambda record: {"state": record.get("state", "LOOK NOW")}
    assert gs528.state_with_entry_contract(
        original,
        {"state": "LOOK NOW"},
    ) == {"state": "LOOK NOW"}
    assert gs528.install() is None


def test_phase56_facade_is_lazy_not_eager():
    source = (
        ROOT / "mide/gs528_canonical_entry_ready.py"
    ).read_text(encoding="utf-8")

    assert "Compatibility shim" in source
    assert "def _entry_authority(" in source
    assert "from .authorities.entry_authority import (" not in source
    assert "from mide.authorities.entry_authority import (" not in source


def test_phase56_entry_meaning_remains_in_entry_authority():
    authority = (
        ROOT / "mide/authorities/entry_authority.py"
    ).read_text(encoding="utf-8")
    facade = (
        ROOT / "mide/gs528_canonical_entry_ready.py"
    ).read_text(encoding="utf-8")

    for name in (
        "canonical_candidate_status",
        "entry_contract",
        "state_with_entry_contract",
        "install",
    ):
        assert f"def {name}(" in authority

    forbidden = (
        "qualified_for_entry =",
        "qualified_for_alert =",
        "qualified_for_watch =",
        "place_order(",
        "submit_order(",
        ".get_bars(",
        ".history(",
    )
    assert not any(token in facade for token in forbidden)

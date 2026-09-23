"""Phase 3 ownership contract for canonical Entry Authority."""

from pathlib import Path

from mide.authorities import entry_authority
from mide import gs528_canonical_entry_ready as gs528


def test_gs528_is_a_compatibility_shim_to_entry_authority():
    assert gs528.entry_contract is entry_authority.entry_contract
    assert gs528.canonical_candidate_status is entry_authority.canonical_candidate_status
    assert gs528.state_with_entry_contract is entry_authority.state_with_entry_contract
    assert gs528.install is entry_authority.install


def test_canonical_entry_meaning_lives_in_authority_module():
    authority = Path("mide/authorities/entry_authority.py").read_text(encoding="utf-8")
    legacy = Path("mide/gs528_canonical_entry_ready.py").read_text(encoding="utf-8")

    assert "def entry_contract(" in authority
    assert "def canonical_candidate_status(" in authority
    assert "def state_with_entry_contract(" in authority
    assert "def install(" in authority

    assert "def entry_contract(" not in legacy
    assert "def canonical_candidate_status(" not in legacy
    assert "def state_with_entry_contract(" not in legacy
    assert "def install(" not in legacy

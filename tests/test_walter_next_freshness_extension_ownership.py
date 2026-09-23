"""Phase 7 ownership contract for freshness and extension semantics."""

from pathlib import Path

from mide.authorities import thesis_state
from mide import gs474_fresh_look_now_expiry as gs474
from mide import gs525_fresh_attention_expiry as gs525
from mide import gs526_3m_stretch_semantics as gs526


def test_gs474_is_compatibility_only():
    assert gs474.fresh_look_now_state is thesis_state.fresh_look_now_state
    assert gs474.install is thesis_state.install_fresh_look_now_expiry


def test_gs525_is_compatibility_only():
    assert gs525.thirty_second_flip_age is thesis_state.thirty_second_flip_age
    assert gs525.fresh_higher_maturation is thesis_state.fresh_higher_maturation
    assert gs525.stale_legacy_developing is thesis_state.stale_legacy_developing
    assert gs525.tightened_opportunity_state is thesis_state.tighten_late_attention_state
    assert gs525.install is thesis_state.install_fresh_attention_expiry


def test_gs526_is_compatibility_only():
    assert gs526.fresh_higher_maturation is thesis_state.fresh_higher_maturation
    assert gs526.materially_stretched_developing is thesis_state.materially_stretched_developing
    assert gs526.tightened_opportunity_state is thesis_state.stretch_adjusted_state
    assert gs526.install is thesis_state.install_3m_stretch_semantics


def test_freshness_and_extension_meaning_lives_in_thesis_state():
    authority = Path("mide/authorities/thesis_state.py").read_text(encoding="utf-8")
    for name in (
        "fresh_look_now_state",
        "tighten_late_attention_state",
        "materially_stretched_developing",
        "stretch_adjusted_state",
    ):
        assert f"def {name}(" in authority

    for path in (
        "mide/gs474_fresh_look_now_expiry.py",
        "mide/gs525_fresh_attention_expiry.py",
        "mide/gs526_3m_stretch_semantics.py",
    ):
        legacy = Path(path).read_text(encoding="utf-8")
        assert "Compatibility shim" in legacy

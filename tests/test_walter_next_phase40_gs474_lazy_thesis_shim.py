"""Phase 40: GS474 is a lazy identity-preserving Thesis / State shim."""

from pathlib import Path
from types import SimpleNamespace

from mide import gs474_fresh_look_now_expiry as gs474
from mide.authorities import thesis_state


ROOT = Path(__file__).resolve().parents[1]


def test_gs474_exports_exact_thesis_state_functions():
    assert gs474.fresh_look_now_state is thesis_state.fresh_look_now_state
    assert gs474.install is thesis_state.install_fresh_look_now_expiry


def test_gs474_stale_generation_gets_safe_noop_installer(monkeypatch):
    monkeypatch.setattr(gs474, "_thesis", lambda: SimpleNamespace())

    assert gs474.__getattr__("install")() is None


def test_phase40_shim_is_lazy_and_definition_free_for_owned_semantics():
    source = (
        ROOT / "mide/gs474_fresh_look_now_expiry.py"
    ).read_text(encoding="utf-8")

    assert "Compatibility shim" in source
    assert "def _thesis(" in source
    assert "def fresh_look_now_state(" not in source
    assert "def install(" not in source
    assert "from .authorities.thesis_state import (" not in source


def test_phase40_scope_remains_presentation_urgency_only():
    source = (
        ROOT / "mide/gs474_fresh_look_now_expiry.py"
    ).read_text(encoding="utf-8")
    forbidden = (
        "qualified_for_entry =",
        "qualified_for_alert =",
        "qualified_for_watch =",
        "execute_order",
        "place_order",
        "get_bars(",
        "get_history(",
        "fetch_bars(",
    )
    assert not any(token in source for token in forbidden)

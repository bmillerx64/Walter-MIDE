"""Phase 37: GS467/GS468 are lazy Thesis / State compatibility shims."""

from pathlib import Path
from types import SimpleNamespace

from mide import gs467_look_now_semantic_consolidation as gs467
from mide import gs468_vwap_truth_veto as gs468
from mide.authorities import thesis_state


ROOT = Path(__file__).resolve().parents[1]


def test_gs467_lazy_export_preserves_authority_identity(monkeypatch):
    delegated = lambda original, record: {
        "state": "DEVELOPING",
        "symbol": record["symbol"],
    }
    monkeypatch.setattr(
        thesis_state,
        "consolidated_look_now",
        delegated,
    )

    assert gs467.consolidated_look_now is delegated


def test_gs468_lazy_export_preserves_private_helper_identity(monkeypatch):
    delegated = lambda record, truth: {
        **record,
        "vwap_relation": "below",
        "truth": truth["numeric_below"],
    }
    monkeypatch.setattr(
        thesis_state,
        "_numeric_below_record",
        delegated,
    )

    assert gs468._numeric_below_record is delegated


def test_gs467_install_tolerates_stale_thesis_generation(monkeypatch):
    monkeypatch.setattr(gs467, "_thesis", lambda: SimpleNamespace())

    assert gs467.__getattr__("install")() is None


def test_gs468_install_tolerates_stale_thesis_generation(monkeypatch):
    monkeypatch.setattr(gs468, "_thesis", lambda: SimpleNamespace())

    assert gs468.__getattr__("install")() is None


def test_phase37_shims_are_lazy_not_eager_authority_imports():
    gs467_source = (
        ROOT / "mide/gs467_look_now_semantic_consolidation.py"
    ).read_text(encoding="utf-8")
    gs468_source = (
        ROOT / "mide/gs468_vwap_truth_veto.py"
    ).read_text(encoding="utf-8")

    assert "Compatibility shim" in gs467_source
    assert "Compatibility shim" in gs468_source
    assert "def _thesis(" in gs467_source
    assert "def _thesis(" in gs468_source
    assert "def consolidated_look_now(" not in gs467_source
    assert "def current_vwap_truth(" not in gs468_source
    assert "from .authorities.thesis_state import (" not in gs467_source
    assert "from .authorities.thesis_state import (" not in gs468_source


def test_phase37_scope_remains_presentation_truth_only():
    sources = [
        (
            ROOT / "mide/gs467_look_now_semantic_consolidation.py"
        ).read_text(encoding="utf-8"),
        (
            ROOT / "mide/gs468_vwap_truth_veto.py"
        ).read_text(encoding="utf-8"),
    ]
    forbidden = (
        ".get_bars(",
        ".history(",
        "request_scan(",
        "place_order(",
        "submit_order(",
        "qualified_for_entry =",
        "qualified_for_alert =",
        "qualified_for_watch =",
        "PARTICIPATION_MIN_",
        "NEAR_ST_LINE_PCT =",
        "LOOK_NOW_MAX_VWAP",
    )
    assert not any(
        token in source
        for source in sources
        for token in forbidden
    )

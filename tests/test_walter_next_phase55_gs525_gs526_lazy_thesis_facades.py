"""Phase 55: GS525/GS526 are warm-deploy-safe lazy Thesis / State facades."""

from pathlib import Path
from types import SimpleNamespace

from mide import gs493_3m_st_retest_truth as gs493
from mide import gs525_fresh_attention_expiry as gs525
from mide import gs526_3m_stretch_semantics as gs526
from mide.authorities import thesis_state


ROOT = Path(__file__).resolve().parents[1]


def test_phase55_constants_and_historical_gs493_seam_are_preserved():
    assert gs525.FRESH_30S_ATTENTION_SECONDS == thesis_state.FRESH_30S_ATTENTION_SECONDS
    assert gs526.MAX_DEVELOPING_3M_ST_GAP_PCT == thesis_state.MAX_DEVELOPING_3M_ST_GAP_PCT
    assert gs526.gs493 is gs493


def test_phase55_gs525_stale_thesis_generation_is_nonfatal(monkeypatch):
    monkeypatch.setattr(gs525, "_thesis", lambda: SimpleNamespace())

    original = lambda record: {"state": record.get("state", "DEVELOPING")}
    assert gs525.thirty_second_flip_age({}) is None
    assert gs525.fresh_higher_maturation({}) is False
    assert gs525.stale_legacy_developing({}, {}) is False
    assert gs525.tightened_opportunity_state(original, {"state": "DEVELOPING"}) == {
        "state": "DEVELOPING"
    }
    assert gs525.install() is None


def test_phase55_gs526_stale_thesis_generation_is_nonfatal(monkeypatch):
    monkeypatch.setattr(gs526, "_thesis", lambda: SimpleNamespace())

    original = lambda record: {"state": record.get("state", "DEVELOPING")}
    assert gs526.fresh_higher_maturation({}) is False
    assert gs526.materially_stretched_developing({}, {}) == (False, {})
    assert gs526.tightened_opportunity_state(original, {"state": "DEVELOPING"}) == {
        "state": "DEVELOPING"
    }
    assert gs526.install() is None


def test_phase55_facades_are_lazy_not_eager():
    source525 = (
        ROOT / "mide/gs525_fresh_attention_expiry.py"
    ).read_text(encoding="utf-8")
    source526 = (
        ROOT / "mide/gs526_3m_stretch_semantics.py"
    ).read_text(encoding="utf-8")

    assert "def _thesis(" in source525
    assert "def _thesis(" in source526
    assert "from .authorities.thesis_state import (" not in source525
    assert "from .authorities.thesis_state import (" not in source526


def test_phase55_authority_ownership_and_scope_remain_unchanged():
    thesis = (
        ROOT / "mide/authorities/thesis_state.py"
    ).read_text(encoding="utf-8")
    source525 = (
        ROOT / "mide/gs525_fresh_attention_expiry.py"
    ).read_text(encoding="utf-8")
    source526 = (
        ROOT / "mide/gs526_3m_stretch_semantics.py"
    ).read_text(encoding="utf-8")

    assert "def tighten_late_attention_state(" in thesis
    assert "def install_fresh_attention_expiry(" in thesis
    assert "def stretch_adjusted_state(" in thesis
    assert "def install_3m_stretch_semantics(" in thesis

    forbidden = (
        "qualified_for_entry =",
        "qualified_for_alert =",
        "qualified_for_watch =",
        "mission_rank =",
        "participation_score =",
        "opportunity_score =",
        "place_order(",
        "submit_order(",
        ".get_bars(",
        ".history(",
    )
    assert not any(token in source525 for token in forbidden)
    assert not any(token in source526 for token in forbidden)

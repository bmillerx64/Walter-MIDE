"""Phase 52: GS511 is a warm-deploy-safe lazy Presentation + Audio facade."""

from pathlib import Path
from types import SimpleNamespace

from mide import gs511_entry_window_vwap_truth as gs511
from mide.authorities import presentation_audio


ROOT = Path(__file__).resolve().parents[1]


def test_gs511_lazy_exports_preserve_exact_authority_identity():
    assert (
        gs511._near_vwap
        is presentation_audio.entry_window_near_vwap
    )
    assert (
        gs511._number
        is presentation_audio._entry_window_number
    )
    assert (
        gs511.NEAR_VWAP_MAX_PCT
        == presentation_audio.ENTRY_WINDOW_NEAR_VWAP_MAX_PCT
    )


def test_phase52_install_tolerates_stale_presentation_generation(monkeypatch):
    monkeypatch.setattr(
        gs511,
        "_presentation",
        lambda: SimpleNamespace(),
    )

    assert gs511.install() is None
    assert gs511.NEAR_VWAP_MAX_PCT == 2.0


def test_phase52_facade_is_lazy_not_eager():
    source = (
        ROOT / "mide/gs511_entry_window_vwap_truth.py"
    ).read_text(encoding="utf-8")

    assert "def _presentation(" in source
    assert (
        "from mide.authorities import presentation_audio as _presentation"
        not in source
    )
    assert "def escalation_state(" not in source
    assert "def escalation_snapshot(" not in source


def test_phase52_scope_remains_presentation_only():
    source = (
        ROOT / "mide/gs511_entry_window_vwap_truth.py"
    ).read_text(encoding="utf-8")
    forbidden = (
        "qualified_for_entry =",
        "qualified_for_alert =",
        "qualified_for_watch =",
        "mission_rank =",
        "participation_score =",
        "opportunity_score =",
        "vwap_distance_pct =",
        "supertrend_bullish =",
        "place_order(",
        "submit_order(",
        ".get_bars(",
        ".history(",
    )
    assert not any(token in source for token in forbidden)

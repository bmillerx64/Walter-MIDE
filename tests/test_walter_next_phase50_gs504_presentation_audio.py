"""Phase 50: GS504 browser action synthesis belongs to Presentation + Audio."""

from pathlib import Path
from types import SimpleNamespace

from mide import gs504_distinct_attention_alarm as gs504
from mide.authorities import presentation_audio


ROOT = Path(__file__).resolve().parents[1]


def test_gs504_facade_delegates_markup(monkeypatch):
    monkeypatch.setattr(
        presentation_audio,
        "distinct_attention_markup",
        lambda markup: markup + "::authority",
    )
    assert (
        gs504.distinct_attention_markup("base")
        == "base::authority"
    )


def test_phase50_stale_presentation_generation_is_nonfatal(monkeypatch):
    monkeypatch.setattr(
        gs504,
        "_presentation",
        lambda: SimpleNamespace(),
    )

    assert gs504.distinct_attention_markup("base") == "base"
    assert gs504.install() is None


def test_phase50_presentation_audio_owns_gs504_synthesis():
    authority = (
        ROOT / "mide/authorities/presentation_audio.py"
    ).read_text(encoding="utf-8")
    facade = (
        ROOT / "mide/gs504_distinct_attention_alarm.py"
    ).read_text(encoding="utf-8")

    assert "def distinct_attention_markup(" in authority
    assert "def install_distinct_attention_audio(" in authority
    assert "const gs504AttentionBell" in authority
    assert "const gs504UrgentSiren" in authority

    assert "Compatibility facade" in facade
    assert "def _presentation(" in facade
    assert "const gs504AttentionBell" not in facade
    assert "@wraps(current)" not in facade


def test_phase50_scope_remains_audio_presentation_only():
    source = (
        ROOT / "mide/gs504_distinct_attention_alarm.py"
    ).read_text(encoding="utf-8")
    forbidden = (
        "qualified_for_entry =",
        "qualified_for_alert =",
        "qualified_for_watch =",
        "mission_rank =",
        "participation_score =",
        "expansion_score =",
        "opportunity_score =",
        "catalyst_score =",
        "vwap_distance_pct =",
        "supertrend_bullish =",
        "place_order(",
        "submit_order(",
        "request_scan(",
        ".get_bars(",
        ".history(",
    )
    assert not any(
        token in source
        for token in forbidden
    )

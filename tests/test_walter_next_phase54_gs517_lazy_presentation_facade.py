"""Phase 54: GS517 is a warm-deploy-safe lazy Presentation + Audio facade."""

from pathlib import Path
from types import SimpleNamespace

from mide import gs517_fresh_event_priority as gs517
from mide.authorities import presentation_audio


ROOT = Path(__file__).resolve().parents[1]


def test_gs517_facade_delegates_to_presentation_authority(monkeypatch):
    monkeypatch.setattr(
        presentation_audio,
        "fresh_maturation_event",
        lambda record: record.get("fresh") is True,
    )
    assert gs517.fresh_maturation_event({"fresh": True}) is True
    assert gs517.fresh_maturation_event({"fresh": False}) is False


def test_phase54_stale_presentation_generation_is_nonfatal(monkeypatch):
    monkeypatch.setattr(
        gs517,
        "_presentation",
        lambda: SimpleNamespace(),
    )

    rows = [{"symbol": "A"}, {"symbol": "B"}]
    assert gs517.fresh_maturation_event(rows[0]) is False
    assert gs517.ordered_fresh_event_records(rows) == rows
    assert gs517.ordered_fresh_event_records(
        rows,
        baseline_order=lambda current: list(reversed(current)),
    ) == list(reversed(rows))
    assert gs517.install() is None


def test_phase54_facade_is_lazy_not_eager():
    source = (
        ROOT / "mide/gs517_fresh_event_priority.py"
    ).read_text(encoding="utf-8")

    assert "def _presentation(" in source
    assert (
        "from .authorities import presentation_audio as _presentation"
        not in source
    )
    assert (
        "from mide.authorities import presentation_audio as _presentation"
        not in source
    )


def test_phase54_authority_still_owns_fresh_event_semantics():
    authority = (
        ROOT / "mide/authorities/presentation_audio.py"
    ).read_text(encoding="utf-8")
    facade = (
        ROOT / "mide/gs517_fresh_event_priority.py"
    ).read_text(encoding="utf-8")

    assert "def fresh_maturation_event(" in authority
    assert "def ordered_fresh_event_records(" in authority
    assert 'current("fresh_event")' in facade
    assert "progression_signal" not in facade


def test_phase54_scope_remains_presentation_order_only():
    source = (
        ROOT / "mide/gs517_fresh_event_priority.py"
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

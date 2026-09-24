"""Phase 48: GS495/GS497 are lazy Presentation + Audio facades."""

from pathlib import Path
from types import SimpleNamespace

from mide import gs495_extreme_attention_anti_chase_semantics as gs495
from mide import gs497_rank_aware_attention_order as gs497
from mide.authorities import presentation_audio


ROOT = Path(__file__).resolve().parents[1]


def test_gs495_public_anti_chase_constant_remains_stable():
    assert gs495.ANTI_CHASE_VWAP_DISTANCE_PCT == 2.0


def test_gs495_facade_delegates_extreme_event(monkeypatch):
    expected = {"label": "EXTREME MOVER · WATCH"}
    monkeypatch.setattr(
        presentation_audio,
        "truthful_extreme_market_event",
        lambda original, record: expected,
    )

    assert gs495.truthful_extreme_market_event(
        lambda record: None,
        {"symbol": "SSM"},
    ) is expected


def test_gs497_facade_delegates_rank_order(monkeypatch):
    rows = [{"symbol": "A"}, {"symbol": "B"}]
    monkeypatch.setattr(
        presentation_audio,
        "ordered_rank_aware_records",
        lambda records, baseline_order=None: list(reversed(list(records))),
    )

    assert gs497.ordered_rank_aware_records(rows) == list(reversed(rows))


def test_phase48_installers_tolerate_stale_presentation_generation(monkeypatch):
    monkeypatch.setattr(
        gs495,
        "_presentation",
        lambda: SimpleNamespace(),
    )
    monkeypatch.setattr(
        gs497,
        "_presentation",
        lambda: SimpleNamespace(),
    )

    assert gs495.install() is None
    assert gs497.install() is None


def test_phase48_facades_are_lazy_not_eager_authority_bindings():
    sources = [
        (
            ROOT / "mide/gs495_extreme_attention_anti_chase_semantics.py"
        ).read_text(encoding="utf-8"),
        (
            ROOT / "mide/gs497_rank_aware_attention_order.py"
        ).read_text(encoding="utf-8"),
    ]

    assert all("def _presentation(" in source for source in sources)
    assert all(
        "from .authorities import presentation_audio as _presentation"
        not in source
        for source in sources
    )


def test_phase48_scope_stays_presentation_only():
    sources = [
        (
            ROOT / "mide/gs495_extreme_attention_anti_chase_semantics.py"
        ).read_text(encoding="utf-8"),
        (
            ROOT / "mide/gs497_rank_aware_attention_order.py"
        ).read_text(encoding="utf-8"),
    ]
    forbidden = (
        ".get_bars(",
        ".history(",
        "place_order(",
        "submit_order(",
        "qualified_for_entry =",
        "qualified_for_alert =",
        "participation_score =",
        "expansion_score =",
    )
    assert not any(
        token in source
        for source in sources
        for token in forbidden
    )

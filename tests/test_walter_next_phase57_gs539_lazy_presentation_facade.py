"""Phase 57: GS539 is a warm-deploy-safe lazy Presentation + Audio facade."""

from pathlib import Path
from types import SimpleNamespace

from mide import gs539_pe_strength_order as gs539
from mide.authorities import presentation_audio


ROOT = Path(__file__).resolve().parents[1]


def test_phase57_current_runtime_delegates_to_presentation(monkeypatch):
    monkeypatch.setattr(presentation_audio, "participation_value", lambda _record: 80.0)
    monkeypatch.setattr(presentation_audio, "expansion_value", lambda _record: 60.0)
    monkeypatch.setattr(presentation_audio, "pe_strength_score", lambda _record: 70.0)

    assert gs539.participation_value({}) == 80.0
    assert gs539.expansion_value({}) == 60.0
    assert gs539.pe_strength_score({}) == 70.0


def test_phase57_stale_presentation_generation_is_nonfatal(monkeypatch):
    monkeypatch.setattr(gs539, "_presentation", lambda: SimpleNamespace())

    rows = [{"symbol": "A"}, {"symbol": "B"}]
    assert gs539.participation_value({}) is None
    assert gs539.expansion_value({}) is None
    assert gs539.pe_strength_score({}) is None
    assert gs539.ordered_pe_strength_records(rows) == rows
    assert gs539.ordered_pe_strength_records(
        rows,
        baseline_order=lambda current: list(reversed(current)),
    ) == list(reversed(rows))

    original = lambda record: {"state": record.get("state", "DEVELOPING")}
    assert gs539.state_with_pe_strength(
        original,
        {"state": "DEVELOPING"},
    ) == {"state": "DEVELOPING"}
    assert gs539.install() is None


def test_phase57_facade_is_lazy_not_eager():
    source = (
        ROOT / "mide/gs539_pe_strength_order.py"
    ).read_text(encoding="utf-8")

    assert "def _presentation(" in source
    assert (
        "from .authorities import presentation_audio as _presentation"
        not in source
    )


def test_phase57_presentation_still_owns_pe_strength_semantics():
    authority = (
        ROOT / "mide/authorities/presentation_audio.py"
    ).read_text(encoding="utf-8")
    facade = (
        ROOT / "mide/gs539_pe_strength_order.py"
    ).read_text(encoding="utf-8")

    for name in (
        "participation_value",
        "expansion_value",
        "pe_strength_score",
        "ordered_pe_strength_records",
        "state_with_pe_strength",
        "install_pe_strength_order",
    ):
        assert f"def {name}(" in authority

    forbidden = (
        "qualified_for_entry =",
        "participation_surge_score =",
        "participation_score =",
        "expansion_quality =",
        "expansion_score =",
        "mission_rank =",
        "place_order(",
        "submit_order(",
        "play_alert(",
    )
    assert not any(token in facade for token in forbidden)

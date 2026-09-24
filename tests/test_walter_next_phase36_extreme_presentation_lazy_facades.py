"""Phase 36: GS465/GS466 are lazy Presentation + Audio facades."""

from pathlib import Path
from types import SimpleNamespace

from mide import gs465_presentation_priority_cleanup as gs465
from mide import gs466_extreme_awareness_continuity as gs466
from mide.authorities import presentation_audio


ROOT = Path(__file__).resolve().parents[1]


def test_gs465_historical_bands_remain_stable_public_contract():
    assert gs465.WATCH_FOR_ENTRY_BAND == 60
    assert gs465.LOOK_NOW_BAND == 50
    assert gs465.DEVELOPING_BAND == 40
    assert gs465.CHASE_WAIT_BAND == 30
    assert gs465.HALTED_BAND == 20
    assert gs465.OTHER_BAND == 10


def test_gs465_facade_delegates_private_specific_look_now(monkeypatch):
    monkeypatch.setattr(
        presentation_audio,
        "_specific_extreme_look_now",
        lambda view: view.get("specific") is True,
    )

    assert gs465._specific_look_now({"specific": True}) is True
    assert gs465._specific_look_now({"specific": False}) is False


def test_gs465_facade_delegates_non_extreme_actionable_helper(monkeypatch):
    monkeypatch.setattr(
        presentation_audio,
        "_non_extreme_actionable_symbols",
        lambda rows, extreme: {
            row["symbol"]
            for row in rows
            if row["symbol"] not in extreme
        },
    )

    result = gs465._non_extreme_actionable_symbols(
        [{"symbol": "A"}, {"symbol": "B"}],
        {"A"},
    )
    assert result == {"B"}


def test_gs465_install_tolerates_stale_authority_generation(monkeypatch):
    monkeypatch.setattr(gs465, "_presentation", lambda: SimpleNamespace())

    assert gs465.install() is None


def test_gs466_install_tolerates_stale_authority_generation(monkeypatch):
    monkeypatch.setattr(gs466, "_presentation", lambda: SimpleNamespace())

    assert gs466.install() is None


def test_gs466_facade_delegates_awareness_semantics(monkeypatch):
    monkeypatch.setattr(
        presentation_audio,
        "extreme_awareness_continuity",
        lambda record, *, base_reason: (
            record["symbol"] == "DLXY"
            and base_reason.startswith("source bar is ")
        ),
    )

    assert gs466.extreme_awareness_continuity(
        {"symbol": "DLXY"},
        base_reason="source bar is 304s old",
    ) is True


def test_phase36_facades_are_lazy_and_do_not_duplicate_presentation_logic():
    gs465_source = (
        ROOT / "mide/gs465_presentation_priority_cleanup.py"
    ).read_text(encoding="utf-8")
    gs466_source = (
        ROOT / "mide/gs466_extreme_awareness_continuity.py"
    ).read_text(encoding="utf-8")

    assert "def _presentation(" in gs465_source
    assert "def _presentation(" in gs466_source
    assert "from .authorities import presentation_audio as _presentation" not in gs465_source
    assert "from .authorities import presentation_audio as _presentation" not in gs466_source
    assert "priority_states = {" not in gs465_source
    assert "generic = (" not in gs465_source
    assert "operator_visibility_reason(record" not in gs466_source


def test_phase36_scope_stays_presentation_only():
    sources = [
        (
            ROOT / "mide/gs465_presentation_priority_cleanup.py"
        ).read_text(encoding="utf-8"),
        (
            ROOT / "mide/gs466_extreme_awareness_continuity.py"
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
        "LOOK_NOW_MAX_VWAP",
    )
    assert not any(
        token in source
        for source in sources
        for token in forbidden
    )

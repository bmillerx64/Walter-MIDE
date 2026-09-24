"""Phase 49: Stage 8 Mission Ranking direction belongs to Thesis / State."""

from pathlib import Path
from types import SimpleNamespace

from mide import gs498_mission_ranking_direction as gs498
from mide.authorities import thesis_state


ROOT = Path(__file__).resolve().parents[1]


def test_thesis_state_owns_strongest_first_mission_ranking():
    weak = {"symbol": "WEAK", "current_momentum": 41.0}
    strong = {"symbol": "STRONG", "current_momentum": 56.0}

    ranked = thesis_state.mission_ranked_records(
        [weak, strong]
    )
    assert [row["symbol"] for row in ranked] == [
        "STRONG",
        "WEAK",
    ]


def test_gs498_facade_delegates_current_authority(monkeypatch):
    marker = [{"symbol": "AUTHORITY"}]
    monkeypatch.setattr(
        thesis_state,
        "mission_ranked_records",
        lambda records: marker,
    )

    assert gs498.mission_ranked_records(
        [{"symbol": "OTHER"}]
    ) is marker


def test_gs498_stale_thesis_generation_avoids_getattr_recursion(monkeypatch):
    stale = SimpleNamespace()
    monkeypatch.setattr(
        gs498,
        "_thesis",
        lambda: stale,
    )

    weak = {"symbol": "WEAK", "current_momentum": 41.0}
    strong = {"symbol": "STRONG", "current_momentum": 56.0}
    ranked = gs498.mission_ranked_records(
        [weak, strong]
    )
    assert [row["symbol"] for row in ranked] == [
        "STRONG",
        "WEAK",
    ]


def test_phase49_authority_no_longer_points_back_to_gs498():
    authority = (
        ROOT / "mide/authorities/thesis_state.py"
    ).read_text(encoding="utf-8")
    facade = (
        ROOT / "mide/gs498_mission_ranking_direction.py"
    ).read_text(encoding="utf-8")

    assert "def mission_ranked_records(" in authority
    assert (
        'if name == "mission_ranked_records"'
        not in authority
    )
    assert "def _thesis(" in facade


def test_phase49_scope_remains_ranking_direction_only():
    source = (
        ROOT / "mide/gs498_mission_ranking_direction.py"
    ).read_text(encoding="utf-8")
    forbidden = (
        "qualified_for_entry =",
        "qualified_for_alert =",
        "qualified_for_watch =",
        "participation_score =",
        "expansion_score =",
        "vwap_distance_pct =",
        "supertrend_bullish =",
        "place_order(",
        "submit_order(",
        "play_alert(",
        ".get_bars(",
        ".history(",
    )
    assert not any(token in source for token in forbidden)
    assert "reverse=True" in source

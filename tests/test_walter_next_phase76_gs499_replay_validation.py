"""Phase 76: GS499 Candidate History compaction belongs to Replay / Validation."""

from pathlib import Path
from types import SimpleNamespace

from mide import gs499_candidate_history_containment as gs499
from mide.authorities import replay_validation


ROOT = Path(__file__).resolve().parents[1]


def test_phase76_authority_preserves_history_limits():
    source = {
        "architecture_audit": list(range(20)),
        "ranking_history": list(range(10)),
        "discovery_history": list(range(10)),
        "reevaluation_history": list(range(10)),
        "current_momentum": 72.0,
    }
    compacted = replay_validation.compact_candidate_history_record(source)

    assert compacted["architecture_audit"] == list(range(12, 20))
    assert compacted["ranking_history"] == [8, 9]
    assert compacted["discovery_history"] == [8, 9]
    assert compacted["reevaluation_history"] == [8, 9]
    assert compacted["current_momentum"] == 72.0


def test_phase76_authority_does_not_mutate_live_record():
    source = {
        "architecture_audit": list(range(20)),
        "ranking_history": list(range(10)),
    }
    replay_validation.compact_candidate_history_record(source)
    assert len(source["architecture_audit"]) == 20
    assert len(source["ranking_history"]) == 10


def test_phase76_legacy_public_name_delegates_lazily(monkeypatch):
    sentinel = {"symbol": "AUTH"}
    monkeypatch.setattr(
        replay_validation,
        "compact_candidate_history_record",
        lambda _record: dict(sentinel),
    )
    assert gs499.compact_candidate_history_record({}) == sentinel


def test_phase76_stale_replay_generation_preserves_local_fallback(monkeypatch):
    monkeypatch.setattr(
        gs499,
        "_replay_validation",
        lambda: SimpleNamespace(),
    )
    compacted = gs499.compact_candidate_history_record(
        {
            "architecture_audit": list(range(12)),
            "ranking_history": list(range(5)),
        }
    )
    assert compacted["architecture_audit"] == list(range(4, 12))
    assert compacted["ranking_history"] == [3, 4]


def test_phase76_compaction_meaning_lives_in_replay_validation():
    legacy = (
        ROOT / "mide/gs499_candidate_history_containment.py"
    ).read_text(encoding="utf-8")
    authority = (
        ROOT / "mide/authorities/replay_validation.py"
    ).read_text(encoding="utf-8")

    assert "def compact_candidate_history_record(" in authority
    assert "CANDIDATE_HISTORY_LIMITS" in authority
    assert '"compact_candidate_history_record"' in legacy


def test_phase76_scope_is_persistence_only():
    source = (
        ROOT / "mide/authorities/replay_validation.py"
    ).read_text(encoding="utf-8")
    start = source.index("# GS499 Candidate History persistence containment")
    end = source.index("# GS458 Flight Recorder fragment freshness lifecycle", start)
    block = source[start:end]

    forbidden = (
        "qualified_for_entry =",
        "qualified_for_alert =",
        "qualified_for_watch =",
        "mission_rank =",
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
    assert not any(token in block for token in forbidden)

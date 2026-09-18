import json
from pathlib import Path

from mide.gs499_candidate_history_containment import (
    compact_candidate_history_record,
)
from mide.memory import MemoryStore


def _record(symbol="WALT", count=40):
    return {
        "symbol": symbol,
        "status": "Watching",
        "candidate_status": "Strengthening",
        "current_momentum": 72.0,
        "opportunity_score": 68.0,
        "architecture_audit": [{"n": i, "payload": "x" * 100} for i in range(count * 8)],
        "ranking_history": [{"n": i} for i in range(count)],
        "discovery_history": [{"n": i} for i in range(count)],
        "reevaluation_history": [{"n": i} for i in range(count)],
        "trigger_diagnostics": {"passed": False, "checks": [{"condition": "VWAP"}]},
    }


def test_compaction_caps_only_cumulative_nested_histories():
    source = _record(count=40)
    compacted = compact_candidate_history_record(source)

    assert len(compacted["architecture_audit"]) == 8
    assert len(compacted["ranking_history"]) == 2
    assert len(compacted["discovery_history"]) == 2
    assert len(compacted["reevaluation_history"]) == 2

    assert compacted["architecture_audit"][0]["n"] == 312
    assert compacted["ranking_history"][0]["n"] == 38
    assert compacted["current_momentum"] == source["current_momentum"]
    assert compacted["trigger_diagnostics"] == source["trigger_diagnostics"]


def test_compaction_does_not_mutate_live_ledger_record():
    source = _record(count=25)
    original_lengths = {
        key: len(source[key])
        for key in (
            "architecture_audit",
            "ranking_history",
            "discovery_history",
            "reevaluation_history",
        )
    }

    compact_candidate_history_record(source)

    assert {
        key: len(source[key])
        for key in original_lengths
    } == original_lengths


def test_memory_store_append_persists_bounded_projection(tmp_path):
    path = tmp_path / "candidate_history.jsonl"
    store = MemoryStore(path)
    source = _record(count=60)

    store.append([source])

    persisted = json.loads(path.read_text(encoding="utf-8").strip())
    assert persisted["symbol"] == "WALT"
    assert persisted["candidate_status"] == "Strengthening"
    assert persisted["current_momentum"] == 72.0
    assert len(persisted["architecture_audit"]) == 8
    assert len(persisted["ranking_history"]) == 2
    assert len(persisted["discovery_history"]) == 2
    assert len(persisted["reevaluation_history"]) == 2

    latest = store.latest_by_symbol()
    assert latest["WALT"]["current_momentum"] == 72.0
    assert latest["WALT"]["candidate_status"] == "Strengthening"


def test_persisted_row_stays_bounded_as_live_history_grows():
    small_source = _record(count=5)
    large_source = _record(count=500)
    small = compact_candidate_history_record(small_source)
    large = compact_candidate_history_record(large_source)

    small_bytes = len(json.dumps(small, default=str))
    large_bytes = len(json.dumps(large, default=str))
    raw_large_bytes = len(json.dumps(large_source, default=str))

    # Once the retained tails are full, persistence size is effectively flat.
    # Larger sequence numbers can add a few digits, but lifetime history length
    # must no longer drive row size.
    assert large_bytes <= small_bytes + 100
    assert large_bytes < raw_large_bytes * 0.05


def test_scope_lock_is_persistence_only():
    source = Path("mide/gs499_candidate_history_containment.py").read_text(
        encoding="utf-8"
    )
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
    assert not any(token in source for token in forbidden)

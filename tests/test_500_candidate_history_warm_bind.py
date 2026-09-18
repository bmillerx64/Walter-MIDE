from pathlib import Path

from mide.gs500_candidate_history_warm_bind import install_for_store_class


def _record(count=100):
    return {
        "symbol": "WALT",
        "architecture_audit": [{"n": i} for i in range(count * 8)],
        "ranking_history": [{"n": i} for i in range(count)],
        "discovery_history": [{"n": i} for i in range(count)],
        "reevaluation_history": [{"n": i} for i in range(count)],
        "current_momentum": 77.0,
    }


def test_warm_bind_compacts_records_before_legacy_append_without_mutating_source():
    captured = []

    class LegacyStore:
        def append(self, records):
            captured.extend(records)

    install_for_store_class(LegacyStore)
    source = _record(100)
    original_lengths = {
        key: len(source[key])
        for key in (
            "architecture_audit",
            "ranking_history",
            "discovery_history",
            "reevaluation_history",
        )
    }

    LegacyStore().append([source])

    assert len(captured) == 1
    persisted = captured[0]
    assert len(persisted["architecture_audit"]) == 8
    assert len(persisted["ranking_history"]) == 2
    assert len(persisted["discovery_history"]) == 2
    assert len(persisted["reevaluation_history"]) == 2
    assert persisted["current_momentum"] == 77.0
    assert {
        key: len(source[key])
        for key in original_lengths
    } == original_lengths


def test_warm_bind_is_idempotent():
    class Store:
        calls = 0

        def append(self, records):
            type(self).calls += 1

    install_for_store_class(Store)
    first = Store.append
    install_for_store_class(Store)
    second = Store.append

    assert first is second
    Store().append([_record(10)])
    assert Store.calls == 1


def test_app_hard_binds_before_memory_store_import():
    app = Path("app.py").read_text(encoding="utf-8")
    bind = "from mide.gs500_candidate_history_warm_bind import install as _install_gs500_candidate_history"
    call = "_install_gs500_candidate_history()"
    memory_import = "from mide.memory import MemoryStore"

    assert bind in app
    assert call in app
    assert app.index(call) < app.index(memory_import)


def test_scope_lock_is_persistence_only():
    source = Path("mide/gs500_candidate_history_warm_bind.py").read_text(
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

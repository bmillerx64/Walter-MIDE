from datetime import datetime, timedelta, timezone

import mide.completed_scan as completed_scan_module
from mide.completed_scan import CompletedScan, completed_scan_for_view, store_completed_scan
from mide.session_controls import (
    DATA_MODE_KEY,
    PROVIDER_KEY,
    SCAN_REQUESTED_AT_KEY,
    SCAN_REQUESTED_KEY,
)


def _scan(symbol: str, *, completed_at: datetime) -> CompletedScan:
    return CompletedScan(
        provider="WEBULL",
        records=[{"symbol": symbol}],
        diagnostics={"scan_completed": True, "marker": symbol},
        warnings=[],
        symbols_sampled=20,
        prefilter_count=5,
        completed_at=completed_at,
        source_label="Live WEBULL",
    )


def _live_state() -> dict:
    return {
        DATA_MODE_KEY: "Live Webull",
        PROVIDER_KEY: "WEBULL",
    }


def test_new_live_session_adopts_process_completed_scan_instead_of_owing_duplicate_work(monkeypatch):
    monkeypatch.setattr(completed_scan_module, "_PROCESS_LIVE_SCAN", None)
    now = datetime.now(timezone.utc)
    owner_state = _live_state()
    completed = _scan("OWNER", completed_at=now)
    store_completed_scan(owner_state, completed)

    arriving_state = _live_state()
    adopted = completed_scan_for_view(arriving_state, "scheduler")

    assert adopted is not None
    assert adopted.records[0]["symbol"] == "OWNER"
    assert adopted.completed_at == completed.completed_at
    assert arriving_state["completed_scan"] is adopted
    assert adopted is not completed


def test_fresher_process_result_clears_only_stale_scheduler_request(monkeypatch):
    monkeypatch.setattr(completed_scan_module, "_PROCESS_LIVE_SCAN", None)
    now = datetime.now(timezone.utc)
    owner_state = _live_state()
    store_completed_scan(owner_state, _scan("FRESH", completed_at=now))

    arriving_state = _live_state()
    arriving_state[SCAN_REQUESTED_KEY] = True
    assert SCAN_REQUESTED_AT_KEY not in arriving_state

    adopted = completed_scan_for_view(arriving_state, "scheduler")

    assert adopted.records[0]["symbol"] == "FRESH"
    assert arriving_state[SCAN_REQUESTED_KEY] is False


def test_process_handoff_never_erases_explicit_manual_scan_request(monkeypatch):
    monkeypatch.setattr(completed_scan_module, "_PROCESS_LIVE_SCAN", None)
    now = datetime.now(timezone.utc)
    owner_state = _live_state()
    store_completed_scan(owner_state, _scan("FRESH", completed_at=now))

    arriving_state = _live_state()
    arriving_state[SCAN_REQUESTED_KEY] = True
    arriving_state[SCAN_REQUESTED_AT_KEY] = now.timestamp()

    adopted = completed_scan_for_view(arriving_state, "scheduler")

    assert adopted.records[0]["symbol"] == "FRESH"
    assert arriving_state[SCAN_REQUESTED_KEY] is True
    assert arriving_state[SCAN_REQUESTED_AT_KEY] == now.timestamp()


def test_process_handoff_never_replaces_newer_local_completed_scan(monkeypatch):
    monkeypatch.setattr(completed_scan_module, "_PROCESS_LIVE_SCAN", None)
    now = datetime.now(timezone.utc)
    owner_state = _live_state()
    store_completed_scan(owner_state, _scan("OLDER", completed_at=now))

    local_state = _live_state()
    newer = _scan("NEWER", completed_at=now + timedelta(seconds=10))
    # Install the local result without publishing it process-wide so this test
    # exercises the read-side freshness guard directly.
    context = completed_scan_module.scan_context(local_state)
    context.completed_scan = newer
    local_state["completed_scan"] = newer

    observed = completed_scan_for_view(local_state, "Radar")

    assert observed is newer
    assert observed.records[0]["symbol"] == "NEWER"


def test_demo_session_does_not_adopt_live_process_result(monkeypatch):
    monkeypatch.setattr(completed_scan_module, "_PROCESS_LIVE_SCAN", None)
    now = datetime.now(timezone.utc)
    owner_state = _live_state()
    store_completed_scan(owner_state, _scan("LIVE", completed_at=now))

    demo_state = {DATA_MODE_KEY: "Demo", PROVIDER_KEY: None}

    assert completed_scan_for_view(demo_state, "Radar") is None


def test_adopted_result_is_detached_from_process_snapshot(monkeypatch):
    monkeypatch.setattr(completed_scan_module, "_PROCESS_LIVE_SCAN", None)
    now = datetime.now(timezone.utc)
    owner_state = _live_state()
    store_completed_scan(owner_state, _scan("SAFE", completed_at=now))

    first_state = _live_state()
    first = completed_scan_for_view(first_state, "Radar")
    first.diagnostics["marker"] = "mutated in first session"

    second_state = _live_state()
    second = completed_scan_for_view(second_state, "Radar")

    assert second.diagnostics["marker"] == "SAFE"

def test_current_local_scan_avoids_redundant_process_deepcopy(monkeypatch):
    monkeypatch.setattr(completed_scan_module, "_PROCESS_LIVE_SCAN", None)
    now = datetime.now(timezone.utc)
    owner_state = _live_state()
    store_completed_scan(owner_state, _scan("CURRENT", completed_at=now))

    local_state = _live_state()
    adopted = completed_scan_for_view(local_state, "initial")
    assert adopted is not None

    original_deepcopy = completed_scan_module.copy.deepcopy
    copies = {"count": 0}

    def counted_deepcopy(value):
        copies["count"] += 1
        return original_deepcopy(value)

    monkeypatch.setattr(completed_scan_module.copy, "deepcopy", counted_deepcopy)

    for view in ("Radar", "header", "runtime health", "GS312 scan timing"):
        observed = completed_scan_for_view(local_state, view)
        assert observed is adopted

    assert copies["count"] == 0


def test_newer_process_scan_is_detached_exactly_once_when_adopted(monkeypatch):
    monkeypatch.setattr(completed_scan_module, "_PROCESS_LIVE_SCAN", None)
    now = datetime.now(timezone.utc)

    local_state = _live_state()
    local_context = completed_scan_module.scan_context(local_state)
    local = _scan("OLD", completed_at=now)
    local_context.completed_scan = local
    local_state["completed_scan"] = local

    owner_state = _live_state()
    store_completed_scan(
        owner_state,
        _scan("NEW", completed_at=now + timedelta(seconds=60)),
    )

    original_deepcopy = completed_scan_module.copy.deepcopy
    copies = {"count": 0}

    def counted_deepcopy(value):
        copies["count"] += 1
        return original_deepcopy(value)

    monkeypatch.setattr(completed_scan_module.copy, "deepcopy", counted_deepcopy)

    adopted = completed_scan_for_view(local_state, "process observer")
    assert adopted.records[0]["symbol"] == "NEW"
    assert copies["count"] == 1

    again = completed_scan_for_view(local_state, "Radar")
    assert again is adopted
    assert copies["count"] == 1


from __future__ import annotations

import json
from types import SimpleNamespace

from mide import flight_recorder
from mide import gs427_flight_recorder_latency_hard_bind as gs427


def _settings():
    return SimpleNamespace(
        min_price=0.02,
        max_price=5.0,
        min_pct_change=3.0,
        min_day_volume=100_000,
        max_free_float=50_000_000,
    )


def test_walk_functions_reaches_base_function_hidden_in_unwrapped_closure():
    def base():
        return "base"

    def make_wrapper(original):
        def wrapper():
            return original()

        return wrapper

    wrapper = make_wrapper(base)

    found = gs427._walk_functions(wrapper)

    assert wrapper in found
    assert base in found


def test_active_recorder_globals_locates_real_flight_recorder_persistence_binding():
    globals_dict = gs427._active_recorder_globals()

    assert globals_dict.get("__name__") == "mide.flight_recorder"
    assert callable(globals_dict.get("persist_replayable_scan"))


def test_install_marks_exact_persistence_binding_used_by_active_recorder():
    gs427.install()

    globals_dict = gs427._active_recorder_globals()
    active = globals_dict["persist_replayable_scan"]

    assert getattr(active, "_gs427_flight_recorder_latency_hard_bind", False) is True


def test_real_record_scan_path_persists_latency_truth_and_runtime_identity(tmp_path):
    gs427.install()
    recorder = flight_recorder.FlightRecorder(tmp_path / "flight.jsonl")

    result = recorder.record_scan(
        seeds=[],
        discovery_reasons={},
        snapshots={},
        candidates=[],
        analyzed=[],
        records=[],
        settings=_settings(),
    )

    assert result["latency_truth"]["authority"] == "OBSERVATIONAL_ONLY"
    identity = result["recorder_runtime_identity"]
    assert identity["authority"] == "OBSERVATIONAL_ONLY"
    assert identity["gs427_hard_bind"] is True
    assert identity["binding"] == (
        "FlightRecorder.record_scan.__globals__.persist_replayable_scan"
    )
    assert identity["trading_logic_changed"] is False
    assert identity["loaded_git_sha"]
    assert identity["checkout_git_sha"]

    persisted = json.loads((tmp_path / "flight.jsonl").read_text().splitlines()[-1])
    assert persisted["latency_truth"]["authority"] == "OBSERVATIONAL_ONLY"
    assert persisted["recorder_runtime_identity"]["gs427_hard_bind"] is True


def test_hard_bind_preserves_existing_scan_fields_without_mutating_source(monkeypatch):
    captured = {}
    source = {"scan_id": "scan-427", "symbols": [], "existing": {"kept": True}}

    def base_persist(_recorder, scan, _records, *args, **kwargs):
        captured.update(scan)
        return scan

    globals_dict = gs427._active_recorder_globals()
    original = globals_dict["persist_replayable_scan"]
    monkeypatch.setitem(globals_dict, "persist_replayable_scan", base_persist)
    try:
        gs427.install()
        result = globals_dict["persist_replayable_scan"](object(), source, [])
    finally:
        globals_dict["persist_replayable_scan"] = original

    assert source == {"scan_id": "scan-427", "symbols": [], "existing": {"kept": True}}
    assert result["existing"] == {"kept": True}
    assert captured["recorder_runtime_identity"]["gs427_hard_bind"] is True
    assert captured["latency_truth"]["authority"] == "OBSERVATIONAL_ONLY"

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

from mide import flight_recorder
from mide import gs425_latency_truth_recorder as gs425
from mide.webull_live import LiveWebullProvider


def _provider() -> LiveWebullProvider:
    provider = object.__new__(LiveWebullProvider)
    provider.diagnostics = {
        "pipeline_timing_summary": [
            {"stage": "Participation Assessment", "elapsed_ms": 81234.5}
        ],
        "gs424_warm_scan_history_cache": {
            "authority": "ACQUISITION_OPTIMIZATION_ONLY",
            "reason": "stage6_benchmark",
            "cache_hits": 2,
            "full_seed_symbols": 0,
        },
    }
    provider._snapshot_client = SimpleNamespace(
        history_call_diagnostics={"batch_calls": 7, "single_fallback_calls": 1}
    )
    provider._walter_gs424_history_cache = {
        "anchor": "2026-09-10T08:00:00+00:00|1Min",
        "rows": {"AAA": [{"t": "2026-09-10T20:00:00Z"}]},
    }
    return provider


def test_latency_truth_preserves_existing_timing_and_cache_evidence():
    provider = _provider()
    events = [
        {
            "reason": "stage6_current_session",
            "elapsed_ms": 12000.0,
            "success": True,
        },
        {
            "reason": "stage6_benchmark",
            "elapsed_ms": 4000.0,
            "success": True,
        },
    ]

    truth = gs425.build_latency_truth(provider, events)

    assert truth["authority"] == "OBSERVATIONAL_ONLY"
    assert truth["stage6_history_elapsed_ms"] == 16000.0
    assert truth["slowest_stage6_history_call"]["reason"] == "stage6_current_session"
    assert truth["pipeline_timing_summary"][0]["elapsed_ms"] == 81234.5
    assert truth["history_call_diagnostics"] == {
        "batch_calls": 7,
        "single_fallback_calls": 1,
    }
    assert truth["gs424_last_cache_observation"]["cache_hits"] == 2
    assert truth["gs424_cached_symbol_count"] == 1
    assert truth["provider_instance_token"]
    assert truth["market_data_values_changed"] is False
    assert truth["trading_logic_changed"] is False


def test_install_times_effective_stage6_boundary_and_persists_it(monkeypatch):
    captured = {}

    def base_bars(self, symbols, **kwargs):
        self._snapshot_client.history_call_diagnostics["batch_calls"] += 1
        return {
            symbol: [{"t": "2026-09-10T20:00:00Z", "c": 1.0}]
            for symbol in symbols
        }

    def base_persist(recorder, scan, records, *args, **kwargs):
        captured.update(scan)
        return scan

    monkeypatch.setattr(LiveWebullProvider, "bars", base_bars)
    monkeypatch.setattr(flight_recorder, "persist_replayable_scan", base_persist)
    gs425._TRACE.events = []
    gs425._TRACE.provider = None
    gs425.install()

    provider = _provider()
    provider._snapshot_client.history_call_diagnostics = {
        "batch_calls": 0,
        "single_fallback_calls": 0,
    }
    provider.bars(
        ["AAA", "BBB"],
        start=datetime(2026, 9, 10, 8, 0, tzinfo=timezone.utc),
        timeframe="1Min",
        limit=960,
        force_batch=True,
        history_reason="stage6_current_session",
    )
    flight_recorder.persist_replayable_scan(
        SimpleNamespace(), {"scan_id": "scan-425", "symbols": []}, []
    )

    truth = captured["latency_truth"]
    assert truth["provider_instance_token"] == f"{id(provider):x}"
    assert len(truth["stage6_history_calls"]) == 1
    event = truth["stage6_history_calls"][0]
    assert event["reason"] == "stage6_current_session"
    assert event["symbol_count"] == 2
    assert event["returned_symbols"] == 2
    assert event["returned_rows"] == 2
    assert event["batch_calls_delta"] == 1
    assert event["success"] is True
    assert event["elapsed_ms"] >= 0
    assert gs425._TRACE.events == []
    assert gs425._TRACE.provider is None


def test_failed_history_call_records_class_without_exception_message(monkeypatch):
    def failing_bars(self, symbols, **kwargs):
        raise RuntimeError("secret token should never enter recorder")

    monkeypatch.setattr(LiveWebullProvider, "bars", failing_bars)
    gs425._TRACE.events = []
    gs425._TRACE.provider = None
    gs425.install()
    provider = _provider()

    try:
        provider.bars(
            ["AAA"],
            start=datetime(2026, 9, 10, 8, 0, tzinfo=timezone.utc),
            timeframe="1Min",
            history_reason="stage6_current_session",
        )
    except RuntimeError:
        pass
    else:
        raise AssertionError("expected failing history call")

    event = gs425._TRACE.events[0]
    assert event["success"] is False
    assert event["exception_class"] == "RuntimeError"
    assert "secret" not in str(event).lower()

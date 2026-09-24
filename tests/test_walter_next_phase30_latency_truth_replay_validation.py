"""Phase 30: GS425 live-scan latency truth belongs to Replay / Validation."""

from pathlib import Path
from types import SimpleNamespace

from mide import gs425_latency_truth_recorder as gs425
from mide.authorities import replay_validation


ROOT = Path(__file__).resolve().parents[1]


def test_gs425_latency_truth_delegates_to_replay_validation():
    provider = SimpleNamespace(
        diagnostics={
            "pipeline_timing_summary": [{"stage": "Stage 6", "elapsed_ms": 25.0}],
            "gs424_warm_scan_history_cache": {"cache_hits": 1},
        },
        _snapshot_client=SimpleNamespace(
            history_call_diagnostics={"batch_calls": 2, "single_fallback_calls": 0}
        ),
        _walter_gs424_history_cache={"rows": {"AAA": [{}]}},
    )
    events = [
        {
            "reason": "stage6_current_session",
            "elapsed_ms": 12.5,
            "success": True,
        }
    ]

    facade = gs425.build_latency_truth(provider, events)
    authoritative = replay_validation.build_latency_truth(provider, events)

    assert facade == authoritative
    assert facade["authority"] == "OBSERVATIONAL_ONLY"
    assert facade["stage6_history_elapsed_ms"] == 12.5
    assert facade["trading_logic_changed"] is False


def test_replay_validation_reads_historical_gs425_trace_state():
    class Provider:
        pass

    provider = Provider()
    gs425._TRACE.events = [{"reason": "stage6_current_session", "elapsed_ms": 1.0}]
    gs425._reset_trace(provider)

    assert replay_validation.latency_provider_from_trace() is provider
    assert replay_validation.latency_trace_events() is gs425._TRACE.events


def test_gs425_warm_deploy_install_tolerates_older_replay_generation(monkeypatch):
    stale = SimpleNamespace()
    monkeypatch.setattr(gs425, "_replay", lambda: stale)

    assert gs425.install() is None


def test_gs425_source_is_lazy_facade_not_duplicate_wrapper_implementation():
    source = (ROOT / "mide/gs425_latency_truth_recorder.py").read_text(
        encoding="utf-8"
    )

    assert "def _replay(" in source
    assert "install_latency_truth_recorder" in source
    assert "LiveWebullProvider.bars =" not in source
    assert "flight_recorder.persist_replayable_scan =" not in source
    assert "def bars_with_latency_truth(" not in source
    assert "from mide.authorities import replay_validation as" not in source


def test_phase30_scope_remains_observational_only():
    source = (ROOT / "mide/gs425_latency_truth_recorder.py").read_text(
        encoding="utf-8"
    )
    forbidden = (
        "qualified_for_entry =",
        "qualified_for_alert =",
        "qualified_for_watch =",
        "participation_score =",
        "expansion_score =",
        "opportunity_score =",
        "request_scan(",
        "place_order(",
        "submit_order(",
        "requests.get(",
        "requests.post(",
    )
    assert not any(token in source for token in forbidden)

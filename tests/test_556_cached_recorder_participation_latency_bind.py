"""GS556: exact cached Flight Recorder persistence bind for GS554 timing."""

from pathlib import Path
from types import SimpleNamespace

from mide import gs427_flight_recorder_latency_hard_bind as gs427
from mide import gs487_cached_recorder_instance_bind as gs487
from mide import gs554_participation_latency_breakdown as gs554
from mide import gs556_cached_recorder_participation_latency_bind as gs556


ROOT = Path(__file__).resolve().parents[1]


class Recorder:
    pass


def _provider():
    provider = SimpleNamespace(diagnostics={})
    gs554.record_breakdown(
        provider,
        stage_input_count=42,
        prefilter_output_count=31,
        history_symbol_count=31,
        analyzed_count=29,
        pre_analysis_ms=9.0,
        analyze_candidates_ms=27000.0,
        velocity_enrichment_ms=12.0,
        scanner_v2_ms=850.0,
        decision_materialization_ms=65.0,
        total_ms=27936.0,
    )
    return provider


def test_gs556_wraps_exact_cached_recorder_globals(monkeypatch):
    provider = _provider()
    captured = {}

    def base(_recorder, scan, records, *args, **kwargs):
        captured["scan"] = dict(scan)
        captured["records"] = list(records)
        return captured["scan"]

    retained_globals = {"persist_replayable_scan": base}
    recorder = Recorder()

    monkeypatch.setattr(
        gs487,
        "_exact_recorder_globals",
        lambda _recorder: retained_globals,
    )
    monkeypatch.setattr(
        gs427,
        "_active_provider",
        lambda: (provider, "gs425_stage6_trace"),
    )

    assert gs556.install_for_recorder(recorder) is True
    result = retained_globals["persist_replayable_scan"](
        recorder,
        {"scan_id": "one"},
        [{"symbol": "TEST"}],
    )

    timing = result[gs556.FIELD]
    assert timing["available"] is True
    assert timing["analyze_candidates_ms"] == 27000.0
    assert timing["provider_source"] == "gs425_stage6_trace"
    assert result["scan_id"] == "one"
    assert captured["records"] == [{"symbol": "TEST"}]
    assert gs556.install_for_recorder(recorder) is False


def test_gs556_unknown_cached_recorder_shape_is_nonfatal(monkeypatch):
    monkeypatch.setattr(
        gs487,
        "_exact_recorder_globals",
        lambda _recorder: None,
    )

    assert gs556.install_for_recorder(Recorder()) is False


def test_gs556_record_scan_safely_binds_after_gs487():
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    start = source.index("def record_scan_safely(")
    end = source.index("\ndef flight_recorder_download_bytes", start)
    block = source[start:end]

    gs487_pos = block.index("mide.gs487_cached_recorder_instance_bind")
    gs556_pos = block.index(
        "mide.gs556_cached_recorder_participation_latency_bind"
    )
    record_call = block.index("recorder.record_scan(")

    assert gs487_pos < gs556_pos < record_call
    assert "latency_binder.install_for_recorder(recorder)" in block


def test_gs556_scope_is_observability_only():
    source = (
        ROOT / "mide/gs556_cached_recorder_participation_latency_bind.py"
    ).read_text(encoding="utf-8")

    forbidden = (
        "qualified_for_entry =",
        "qualified_for_alert =",
        "qualified_for_watch =",
        "mission_rank =",
        "participation_score =",
        "expansion_score =",
        "opportunity_state =",
        "place_order(",
        "submit_order(",
        ".bars(",
        ".get_bars(",
        ".history(",
    )
    assert not any(token in source for token in forbidden)

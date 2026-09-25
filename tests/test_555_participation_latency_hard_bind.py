"""GS555: hard-bind GS554 timing into the retained Flight Recorder graph."""

from pathlib import Path
from types import SimpleNamespace

from mide import gs554_participation_latency_breakdown as gs554
from mide import gs555_participation_latency_hard_bind as gs555
from mide import gs427_flight_recorder_latency_hard_bind as gs427


ROOT = Path(__file__).resolve().parents[1]


def _provider():
    provider = SimpleNamespace(diagnostics={})
    gs554.record_breakdown(
        provider,
        stage_input_count=40,
        prefilter_output_count=30,
        history_symbol_count=30,
        analyzed_count=29,
        pre_analysis_ms=12.0,
        analyze_candidates_ms=28000.0,
        velocity_enrichment_ms=14.0,
        scanner_v2_ms=800.0,
        decision_materialization_ms=90.0,
        total_ms=28916.0,
    )
    return provider


def test_gs555_snapshot_reads_existing_gs554_measurement_only():
    payload = gs555.snapshot(_provider(), "gs425_stage6_trace")

    assert payload["available"] is True
    assert payload["analyze_candidates_ms"] == 28000.0
    assert payload["provider_source"] == "gs425_stage6_trace"
    assert payload["gs555_hard_bind"] is True
    assert payload["extra_provider_calls"] == 0
    assert payload["trading_logic_changed"] is False


def test_gs555_snapshot_is_truthful_when_gs554_measurement_missing():
    provider = SimpleNamespace(diagnostics={})

    payload = gs555.snapshot(provider, "unavailable")

    assert payload["available"] is False
    assert "unavailable" in payload["reason"].lower()
    assert payload["extra_provider_calls"] == 0


def test_gs555_install_wraps_exact_retained_recorder_globals(monkeypatch):
    provider = _provider()
    captured = {}

    def base(_recorder, scan, records, *args, **kwargs):
        captured["scan"] = dict(scan)
        captured["records"] = list(records)
        return captured["scan"]

    retained_globals = {"persist_replayable_scan": base}

    monkeypatch.setattr(gs427, "_active_recorder_globals", lambda: retained_globals)
    monkeypatch.setattr(
        gs427,
        "_active_provider",
        lambda: (provider, "gs425_stage6_trace"),
    )

    assert gs555.install() is True
    result = retained_globals["persist_replayable_scan"](
        object(),
        {"scan_id": "one"},
        [{"symbol": "TEST"}],
    )

    timing = result[gs555.FIELD]
    assert timing["available"] is True
    assert timing["total_ms"] == 28916.0
    assert result["scan_id"] == "one"
    assert captured["records"] == [{"symbol": "TEST"}]
    assert gs555.install() is False


def test_gs555_app_reasserts_hard_bind_at_app_entry():
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    entry = source.index('log_startup("entering app.py")')
    bind = source.index("mide.gs555_participation_latency_hard_bind")
    standard_library = source.index("from datetime import datetime")

    assert entry < bind < standard_library
    assert "_install_gs555_participation_latency()" in source[bind:bind + 400]


def test_gs555_scope_is_observability_only():
    source = (
        ROOT / "mide/gs555_participation_latency_hard_bind.py"
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

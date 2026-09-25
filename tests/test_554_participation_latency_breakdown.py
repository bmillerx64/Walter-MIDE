"""GS554: decompose Participation latency without changing scan semantics."""

from pathlib import Path

from mide import gs425_latency_truth_recorder as gs425
from mide import gs554_participation_latency_breakdown as gs554


ROOT = Path(__file__).resolve().parents[1]


class Provider:
    def __init__(self):
        self.diagnostics = {}


def test_gs554_records_observational_breakdown_only():
    provider = Provider()

    payload = gs554.record_breakdown(
        provider,
        stage_input_count=39,
        prefilter_output_count=31,
        history_symbol_count=31,
        analyzed_count=28,
        pre_analysis_ms=12.5,
        analyze_candidates_ms=28000.0,
        velocity_enrichment_ms=15.0,
        scanner_v2_ms=1200.0,
        decision_materialization_ms=75.0,
        total_ms=29302.5,
    )

    assert provider.diagnostics[gs554.DIAGNOSTIC_KEY] == payload
    assert payload["authority"] == "OBSERVATIONAL_ONLY"
    assert payload["extra_provider_calls"] == 0
    assert payload["market_data_values_changed"] is False
    assert payload["trading_logic_changed"] is False


def test_gs554_latency_truth_separates_history_io_from_local_analysis():
    provider = Provider()
    gs554.record_breakdown(
        provider,
        stage_input_count=39,
        prefilter_output_count=31,
        history_symbol_count=31,
        analyzed_count=28,
        pre_analysis_ms=20.0,
        analyze_candidates_ms=28100.0,
        velocity_enrichment_ms=10.0,
        scanner_v2_ms=900.0,
        decision_materialization_ms=70.0,
        total_ms=29100.0,
    )

    truth = gs554.augment_latency_truth(
        provider,
        {"stage6_history_elapsed_ms": 1600.0},
    )
    breakdown = truth["participation_latency_breakdown"]

    assert breakdown["stage6_history_elapsed_ms"] == 1600.0
    assert breakdown["analyze_candidates_non_history_ms"] == 26500.0


def test_gs554_install_wraps_retained_gs425_latency_truth(monkeypatch):
    provider = Provider()
    gs554.record_breakdown(
        provider,
        stage_input_count=1,
        prefilter_output_count=1,
        history_symbol_count=1,
        analyzed_count=1,
        pre_analysis_ms=1.0,
        analyze_candidates_ms=50.0,
        velocity_enrichment_ms=2.0,
        scanner_v2_ms=3.0,
        decision_materialization_ms=4.0,
        total_ms=60.0,
    )

    def legacy(_provider, _events=None):
        return {"stage6_history_elapsed_ms": 20.0}

    monkeypatch.setattr(gs425, "build_latency_truth", legacy)

    assert gs554.install() is True
    truth = gs425.build_latency_truth(provider)

    assert truth["participation_latency_breakdown"][
        "analyze_candidates_non_history_ms"
    ] == 30.0
    assert gs554.install() is False


def test_gs554_app_times_existing_participation_subphases():
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    start = source.index("    def participation(records):")
    end = source.index("\n    def expansion(records):", start)
    block = source[start:end]

    assert "gs554_participation_latency_breakdown" in block
    assert "analyze_candidates_ms" in block
    assert "velocity_enrichment_ms" in block
    assert "scanner_v2_ms" in block
    assert "decision_materialization_ms" in block
    assert "record_breakdown(" in block


def test_gs554_scope_is_observation_only():
    source = (
        ROOT / "mide/gs554_participation_latency_breakdown.py"
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

import inspect
import json
import logging
from datetime import datetime, timezone

import pytest

from app import (
    ALERT_VOICE_SESSION_KEY,
    alert_voice_for_session,
    price_gate_savings_metrics,
    print_scan_stage_counts,
    run_live,
)
from mide.completed_scan import CompletedScan
from mide.memory import MemoryStore
from mide.architecture import WalterArchitectureV1
from mide.pipeline_diagnostics import observe_runtime_collection_count
from mide.ui import actionable_candidate_records


class DummyStatus:
    def write(self, message):
        pass

    def update(self, **kwargs):
        pass


class DummyProgress:
    def progress(self, value, text=None):
        pass


class DummyClient:
    warnings = []
    diagnostics = {}

    def news(self, *args, **kwargs):
        return []

    def snapshots(self, symbols):
        return {
            symbol: {
                "latestTrade": {"p": 1.25},
                "float_shares": 2_000_000,
            }
            for symbol in symbols
        }


def test_price_gate_savings_quantifies_symbols_batches_and_observed_time():
    metrics = price_gate_savings_metrics(
        universe_count=420,
        survivor_count=90,
        batch_size=150,
        price_elapsed_ms=40,
        snapshot_elapsed_ms=120,
    )

    assert metrics == {
        "price_gate_input_symbols": 420,
        "snapshot_symbols_requested": 90,
        "snapshot_symbols_avoided": 330,
        "snapshot_symbol_reduction_pct": 78.57,
        "baseline_snapshot_batches": 3,
        "actual_snapshot_batches": 1,
        "snapshot_batches_avoided": 2,
        "price_endpoint_elapsed_ms": 40.0,
        "observed_survivor_snapshot_elapsed_ms": 120.0,
        "estimated_gross_snapshot_time_avoided_ms": 240.0,
        "estimated_net_time_saved_ms": 200.0,
    }


def test_price_gate_savings_does_not_invent_timing_without_snapshot_sample():
    metrics = price_gate_savings_metrics(300, 0, 150, 25, 0)

    assert metrics["snapshot_symbols_avoided"] == 300
    assert metrics["snapshot_batches_avoided"] == 2
    assert metrics["estimated_gross_snapshot_time_avoided_ms"] is None
    assert metrics["estimated_net_time_saved_ms"] is None


def test_scan_stage_instrumentation_prints_only_the_ordered_counts(capsys):
    print_scan_stage_counts({
        "Universe discovered": {"count": 9, "symbols": ["AAA", "BBB", "CCC", "DDD", "EEE"]},
        "Symbols loaded": {"count": 8, "symbols": ["AAA", "BBB", "CCC", "DDD", "EEE"]},
        "Prefiltered": {"count": 7, "symbols": ["AAA", "BBB", "CCC", "DDD", "EEE"]},
        "Candidates": {"count": 6, "symbols": ["AAA", "BBB", "CCC", "DDD", "EEE"]},
        "Analyzed": {"count": 5, "symbols": ["AAA", "BBB", "CCC", "DDD", "EEE"]},
        "Ranked": {"count": 4, "symbols": ["AAA", "BBB", "CCC", "DDD"]},
        "Published": {"count": 3, "symbols": ["AAA", "BBB", "CCC"]},
        "Dashboard": {"count": 2, "symbols": ["AAA", "BBB"]},
    })

    assert capsys.readouterr().out.splitlines() == [
        "Universe discovered\t9\tAAA,BBB,CCC,DDD,EEE",
        "Symbols loaded\t8\tAAA,BBB,CCC,DDD,EEE",
        "Prefiltered\t7\tAAA,BBB,CCC,DDD,EEE",
        "Candidates\t6\tAAA,BBB,CCC,DDD,EEE",
        "Analyzed\t5\tAAA,BBB,CCC,DDD,EEE",
        "Ranked\t4\tAAA,BBB,CCC,DDD",
        "Published\t3\tAAA,BBB,CCC",
        "Dashboard\t2\tAAA,BBB",
    ]


def test_run_live_enrichment_path_passes_previous_state(monkeypatch, tmp_path):
    signature = inspect.signature(MemoryStore.enrich_velocity)
    assert list(signature.parameters) == ["self", "records", "previous"]
    assert signature.parameters["previous"].default is None

    monkeypatch.setattr("app.get_secret", lambda name, default="": "secret")
    monkeypatch.setattr("app.st.status", lambda *args, **kwargs: DummyStatus())
    monkeypatch.setattr("app.st.progress", lambda *args, **kwargs: DummyProgress())
    monkeypatch.setattr(
        "app.build_seed_symbols",
        lambda client, settings, news: (["TEST"], {"TEST": ["seed"]}),
    )
    monkeypatch.setattr(
        "app.prefilter_snapshots", lambda snapshots, settings: [{"symbol": "TEST"}]
    )
    monkeypatch.setattr(
        "app.analyze_candidates",
        lambda client, candidates, news_index, reasons: [
            {
                "symbol": "TEST",
                "opportunity_score": 55,
                "status": "MONITOR",
                "candidate_status": "Watching",
                "scanner_v2_score": 55,
                "volume": 1000,
                "dollar_volume": 50_000,
                "rvol_proxy": 2,
                "vwap_relation": "above",
                "participation_score": 60,
                "volume_acceleration": 1,
                "reasons": [],
                "cautions": [],
                "timeframes": {},
            }
        ],
    )
    history_path = tmp_path / "history.jsonl"
    history_path.write_text(
        json.dumps(
            {
                "symbol": "TEST",
                "opportunity_score": 42,
                "status": "PASS",
                "candidate_status": "Watching",
            }
        )
        + "\n"
    )
    store = MemoryStore(history_path)
    monkeypatch.setattr("app.get_store", lambda: store)

    class BrokenRecorder:
        def record_scan(self, **kwargs):
            assert kwargs["records"] is __import__("app").st.session_state.records
            raise OSError("recorder unavailable")

    monkeypatch.setattr("app.get_flight_recorder", lambda: BrokenRecorder())

    records, seed_count, candidate_count, warnings, diagnostics = run_live(
        "Scanner V2 (adaptive momentum)",
        client_factory=lambda *args, **kwargs: DummyClient(),
        credential_checker=lambda client: "paper",
    )

    assert seed_count == 1
    assert candidate_count == 1
    assert records[0]["previous_score"] == 42
    assert records[0]["velocity"] == 13
    assert records[0]["status_changed"] is True
    assert records[0]["scanner_version"] == "Walter Architecture v1.0"
    assert records[0]["terminal_outcome"] == "Qualified and Ranked"
    assert records[0]["mission_rank"] == 1
    assert [stage["stage"] for stage in diagnostics["walter_architecture"]["stages"]] == [
        "Universe Construction", "Price Gate", "Validity Gate", "Free-Float Gate",
        "Catalyst Assessment", "Participation Assessment", "Expansion Assessment",
        "Mission Ranking and Publication",
    ]
    assert __import__("app").st.session_state.records is records
    assert "flight_recorder_error" not in diagnostics
    assert diagnostics["flight_recorder_runtime"]["invoked"] is True
    assert diagnostics["flight_recorder_runtime"]["record_scan_succeeded"] is False
    assert diagnostics["flight_recorder_runtime"]["exception"] == {
        "class": "OSError",
        "message": "recorder unavailable",
    }
    scan = CompletedScan(
        provider="ALPACA", records=records, diagnostics=diagnostics,
        warnings=warnings, symbols_sampled=seed_count,
        prefilter_count=candidate_count, completed_at=datetime.now(timezone.utc),
        source_label="instrumented live scan",
    )
    observe_runtime_collection_count(
        diagnostics, "CompletedScan.records", scan.records,
        statement="scan = CompletedScan(records=records, ...)",
    )
    actionable = actionable_candidate_records(scan.records)
    observe_runtime_collection_count(
        diagnostics, "actionable_candidate_records(records)", actionable,
        statement="actionable_records = actionable_candidate_records(records)",
    )
    display_records = [
        record for record in actionable
        if record.get("status") not in {"PASS", "Removed"}
    ]
    observe_runtime_collection_count(
        diagnostics, "dashboard render", display_records,
        statement=(
            'display_records = [r for r in actionable_records if r.get("status") '
            'not in {"PASS", "Removed"}]'
        ),
    )
    assert [
        (item["stage"], item["count"], item["change"])
        for item in diagnostics["runtime_collection_counts"]
    ] == [
        ("universe discovered", 1, None),
        ("seeds", 1, 0),
        ("candidates", 1, 0),
        ("analyzed", 1, 0),
        ("ranked", 1, 0),
        ("published", 1, 0),
        ('state["ranked"]', 1, 0),
        ("CompletedScan.records", 1, 0),
        ("actionable_candidate_records(records)", 1, 0),
        ("dashboard render", 1, 0),
    ]
    persisted = [json.loads(line) for line in history_path.read_text().splitlines()]
    assert persisted[-1]["symbol"] == records[0]["symbol"]
    assert persisted[-1]["velocity"] == records[0]["velocity"]


def test_run_live_scanner_v1_enrichment_path_accepts_previous_state(
    monkeypatch, tmp_path
):
    __import__("app").st.session_state.walter_session_universe_cache = {}
    monkeypatch.setattr("app.get_secret", lambda name, default="": "secret")
    monkeypatch.setattr("app.st.status", lambda *args, **kwargs: DummyStatus())
    monkeypatch.setattr("app.st.progress", lambda *args, **kwargs: DummyProgress())
    monkeypatch.setattr(
        "app.build_seed_symbols",
        lambda client, settings, news: (["VONE"], {"VONE": ["seed"]}),
    )
    monkeypatch.setattr(
        "app.prefilter_snapshots", lambda snapshots, settings: [{"symbol": "VONE"}]
    )
    monkeypatch.setattr(
        "app.analyze_candidates",
        lambda client, candidates, news_index, reasons: [
            {
                "symbol": "VONE",
                "opportunity_score": 61,
                "status": "MONITOR",
                "candidate_status": "MONITOR",
                "volume": 1000,
                "dollar_volume": 5000,
                "rvol_proxy": 2,
                "vwap_relation": "above",
                "participation_score": 60,
                "volume_acceleration": 1,
                "reasons": [],
                "cautions": [],
                "timeframes": {},
            }
        ],
    )
    history_path = tmp_path / "history-v1.jsonl"
    history_path.write_text(
        json.dumps(
            {
                "symbol": "VONE",
                "opportunity_score": 50,
                "status": "PASS",
                "candidate_status": "PASS",
            }
        )
        + "\n"
    )
    store = MemoryStore(history_path)
    monkeypatch.setattr("app.get_store", lambda: store)

    records, seed_count, candidate_count, warnings, diagnostics = run_live(
        "Scanner V1 (classic screener)",
        client_factory=lambda *args, **kwargs: DummyClient(),
        credential_checker=lambda client: "paper",
    )

    assert seed_count == 1
    assert candidate_count == 1
    assert records[0]["scanner_version"] == "Walter Architecture v1.0"
    assert records[0]["previous_score"] == 50
    assert records[0]["velocity"] == 11
    assert records[0]["status_changed"] is True
    persisted = [json.loads(line) for line in history_path.read_text().splitlines()]
    assert persisted[-1]["symbol"] == records[0]["symbol"]
    assert persisted[-1]["scanner_version"] == "Walter Architecture v1.0"
    assert persisted[-1]["velocity"] == records[0]["velocity"]


def test_selected_voice_persists_across_multiple_auto_scan_cycles():
    session_state = {ALERT_VOICE_SESSION_KEY: "Samantha"}

    manual_scan_voice = alert_voice_for_session(session_state)
    auto_scan_voices = [alert_voice_for_session(session_state) for _ in range(3)]

    assert manual_scan_voice == "Samantha"
    assert auto_scan_voices == ["Samantha", "Samantha", "Samantha"]


def test_system_default_voice_normalizes_to_browser_default_across_auto_scans():
    session_state = {ALERT_VOICE_SESSION_KEY: "System"}

    assert [alert_voice_for_session(session_state) for _ in range(2)] == ["", ""]


def test_run_live_logs_entire_pipeline_failure_and_closes_status(monkeypatch, caplog):
    status = DummyStatus()
    updates = []
    status.update = lambda **kwargs: updates.append(kwargs)
    monkeypatch.setattr("app.st.status", lambda *args, **kwargs: status)
    monkeypatch.setattr(
        "app._run_live_pipeline",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("stage exploded")),
    )

    with caplog.at_level(logging.ERROR):
        result = run_live()

    assert "Live scan pipeline failed" in caplog.text
    assert "Traceback" in caplog.text
    assert result[:3] == ([], 0, 0)
    assert result[4]["provider_failures"][0]["recovery_action"].startswith("return an empty")
    assert updates == [{
        "label": "Scan failed: RuntimeError: stage exploded",
        "state": "error",
        "expanded": True,
    }, {
        "label": "Scan complete with recovery: RuntimeError",
        "state": "complete",
        "expanded": False,
    }]


def test_live_scan_dispatches_through_walter_architecture(monkeypatch):
    expected = ([], 0, 0, [], {})
    invocations = []
    original_run = WalterArchitectureV1.run

    def observed_run(self):
        invocations.append(self)
        return original_run(self)

    monkeypatch.setattr("app.st.status", lambda *args, **kwargs: DummyStatus())
    monkeypatch.setattr("app._run_live_pipeline", lambda *args, **kwargs: expected)
    monkeypatch.setattr(WalterArchitectureV1, "run", observed_run)

    assert run_live() is expected
    assert len(invocations) == 1
    assert isinstance(invocations[0], WalterArchitectureV1)

import inspect
import json
import logging

import pytest

from app import (
    ALERT_VOICE_SESSION_KEY,
    alert_voice_for_session,
    record_ncra_float_diagnostic,
    run_live,
)
from mide.memory import MemoryStore


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
    assert records[0]["scanner_version"] == "Decision Funnel 3.0"
    assert records[0]["current_stage"] == "Stage 2"
    assert records[0]["candidate_status"] == "Removed"
    assert records[0]["final_decision"] == "Rejected"
    assert records[0]["rejection_reason"] == "Price: Outside permitted range"
    assert __import__("app").st.session_state.records is records
    assert diagnostics["flight_recorder_error"] == "write failed; scan continued"
    persisted = [json.loads(line) for line in history_path.read_text().splitlines()]
    assert persisted[-1]["symbol"] == records[0]["symbol"]
    assert persisted[-1]["velocity"] == records[0]["velocity"]


def test_run_live_scanner_v1_enrichment_path_accepts_previous_state(
    monkeypatch, tmp_path
):
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
    assert records[0]["scanner_version"] == "Decision Funnel 3.0"
    assert records[0]["previous_score"] == 50
    assert records[0]["velocity"] == 11
    assert records[0]["status_changed"] is True
    persisted = [json.loads(line) for line in history_path.read_text().splitlines()]
    assert persisted[-1]["symbol"] == records[0]["symbol"]
    assert persisted[-1]["scanner_version"] == "Decision Funnel 3.0"
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


def test_ncra_missing_float_diagnostic_never_aborts_scan(caplog):
    class DiagnosticFailureClient:
        def __init__(self):
            self.warnings = []

        def free_float_diagnostic(self, symbol):
            raise TimeoutError("provider timed out")

    client = DiagnosticFailureClient()
    rejection = [{
        "symbol": "NCRA",
        "reason": "Free Float",
        "result": "Unavailable",
    }]

    with caplog.at_level(logging.ERROR):
        record_ncra_float_diagnostic(client, rejection)

    assert "live scan continuing" in caplog.text
    assert client.warnings == [
        "NCRA free-float diagnostic unavailable; scan continued: provider timed out"
    ]


def test_run_live_logs_entire_pipeline_failure_and_closes_status(monkeypatch, caplog):
    status = DummyStatus()
    updates = []
    status.update = lambda **kwargs: updates.append(kwargs)
    monkeypatch.setattr("app.st.status", lambda *args, **kwargs: status)
    monkeypatch.setattr(
        "app._run_live_pipeline",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("stage exploded")),
    )

    with caplog.at_level(logging.ERROR), pytest.raises(RuntimeError, match="stage exploded"):
        run_live()

    assert "Live scan pipeline failed" in caplog.text
    assert "Traceback" in caplog.text
    assert updates == [{
        "label": "Scan failed: RuntimeError: stage exploded",
        "state": "error",
        "expanded": True,
    }]

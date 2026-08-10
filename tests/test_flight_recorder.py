from types import SimpleNamespace

from app import (
    flight_recorder_download_bytes,
    record_scan_safely,
    repair_mide_module_links,
)
from mide.flight_recorder import FlightRecorder, STAGES, prefilter_decision
from mide.discovery import prefilter_snapshots

SETTINGS = SimpleNamespace(
    min_price=0.02, max_price=5.0, min_pct_change=5.0, min_day_volume=100_000
)


def snapshot(price=1.0, volume=200_000, previous_close=0.9):
    return {
        "latestTrade": {"p": price},
        "latestQuote": {"bp": price - 0.01, "ap": price + 0.01},
        "dailyBar": {"c": price, "v": volume},
        "prevDailyBar": {"c": previous_close},
    }


def test_prefilter_decision_exposes_exact_measurements_and_thresholds():
    decision = prefilter_decision(
        "LOW", snapshot(volume=10, previous_close=1.0), SETTINGS
    )

    assert decision["passed"] is False
    assert "pct_change 0 < 5" in decision["reason"]
    assert decision["failed_rule"] == (
        "Percent change and average volume below thresholds"
    )
    assert decision["failed_metrics"] == [
        {"metric": "pct_change", "measured": 0.0, "operator": "<", "threshold": 5.0},
        {"metric": "volume", "measured": 10.0, "operator": "<", "threshold": 100_000},
    ]
    assert decision["measured_values"]["volume"] == 10
    assert decision["thresholds"]["min_day_volume"] == 100_000


def test_prefilter_uses_share_volume_not_dollar_volume():
    decision = prefilter_decision(
        "PENNY", snapshot(price=0.25, volume=100_000, previous_close=0.20), SETTINGS
    )

    assert decision["passed"] is True
    assert decision["measured_values"]["dollar_volume"] == 25_000
    assert [candidate["symbol"] for candidate in prefilter_snapshots(
        {"PENNY": snapshot(price=0.25, volume=100_000, previous_close=0.20)},
        SETTINGS,
    )] == ["PENNY"]


def test_recorder_persists_complete_paths_funnel_and_latest_lookup(tmp_path):
    recorder = FlightRecorder(tmp_path / "flights.jsonl")
    gate = {
        "passed": True,
        "reason": "Participation Present",
        "checks": [{"condition": "pace", "measured": 1.4, "threshold": 1.2}],
    }
    structure = {
        "passed": True,
        "reason": "Structure Ready",
        "checks": [
            {"condition": "Near VWAP", "measured": 0.5, "threshold": "-1.0 to 2.5%"}
        ],
    }
    record = {
        "symbol": "PASS",
        "status": "Strengthening",
        "qualified_for_ranking": True,
        "participation_gate": gate,
        "structure_gate": structure,
        "quality_score": 88,
        "quality_grade": "B+",
    }
    scan = recorder.record_scan(
        seeds=["PASS", "DROP"],
        discovery_reasons={"PASS": ["market mover"], "DROP": ["recent news"]},
        snapshots={"PASS": snapshot(), "DROP": snapshot(price=8)},
        candidates=[{"symbol": "PASS"}],
        analyzed=[record],
        records=[record],
        settings=SETTINGS,
        scanner_v2=True,
        recent_news_log=[{"Ticker": "PASS", "News source": "Reuters"}],
    )

    assert scan["funnel"] == {
        "Sampled": 2,
        "Prefiltered": 1,
        "Analyzed": 1,
        "Participation PASS": 1,
        "Structure PASS": 1,
        "Qualified": 1,
        "Displayed": 1,
    }
    assert scan["recent_wire_news"] == [
        {"Ticker": "PASS", "News source": "Reuters"}
    ]
    trace = recorder.latest_for_symbol("drop")
    assert [event["stage"] for event in trace["events"]] == list(STAGES)
    assert trace["events"][2]["passed"] is False
    assert "outside" in trace["events"][2]["reason"]
    assert recorder.latest_for_symbol("missing") is None

    exported = recorder.export_bytes()
    assert scan["scan_id"].encode() in exported
    history = recorder.history_for_symbol("pass")
    assert len(history) == 1
    assert history[0]["scanner_version"] == "V2"
    assert history[0]["stage_reached"] == "actionable display"
    assert history[0]["evidence"]["quality_score"] == 88
    assert history[0]["evidence"]["quality_grade"] == "B+"


def test_recorder_keeps_legacy_schema_when_news_log_is_not_provided(tmp_path):
    recorder = FlightRecorder(tmp_path / "flights.jsonl")

    scan = recorder.record_scan(
        seeds=[],
        discovery_reasons={},
        snapshots={},
        candidates=[],
        analyzed=[],
        records=[],
        settings=SETTINGS,
    )

    assert "recent_wire_news" not in scan
    assert "recent_wire_news" not in recorder.latest_scan()


def test_recorder_persists_expansion_candidate_ledger(tmp_path):
    recorder = FlightRecorder(tmp_path / "flights.jsonl")
    rejected = {
        "symbol": "DROP",
        "participation_score": 41.0,
        "expansion_score": 45,
        "passed": False,
        "decision_booleans": [{
            "boolean": "VWAP", "passed": False, "result": "Failing",
            "metric_values": {"vwap_distance_pct": -3.2},
        }],
        "first_failed_boolean": "VWAP",
    }

    scan = recorder.record_scan(
        seeds=[], discovery_reasons={}, snapshots={}, candidates=[], analyzed=[],
        records=[], settings=SETTINGS, expansion_candidate_ledger=[rejected],
    )

    assert scan["expansion_candidate_ledger"] == [rejected]
    assert recorder.latest_scan()["expansion_candidate_ledger"][0]["symbol"] == "DROP"


def test_safe_record_scan_retries_legacy_interface_without_news():
    class LegacyRecorder:
        def __init__(self):
            self.calls = []

        def record_scan(self, **kwargs):
            if "recent_news_log" in kwargs:
                raise TypeError(
                    "record_scan() got an unexpected keyword argument 'recent_news_log'"
                )
            self.calls.append(kwargs)
            return {"scan_id": "legacy"}

    recorder = LegacyRecorder()
    result = record_scan_safely(
        recorder, recent_news_log=[{"Ticker": "NEWS"}], records=[]
    )

    assert result == {"scan_id": "legacy"}
    assert recorder.calls == [{"records": []}]


def test_safe_record_scan_logs_and_swallows_write_failure(caplog):
    class BrokenRecorder:
        path = None

        def record_scan(self, **kwargs):
            raise OSError("disk unavailable; token=do-not-expose")

    diagnostics = {}
    with caplog.at_level("ERROR", logger="app"):
        result = record_scan_safely(
            BrokenRecorder(), records=[], runtime_diagnostics=diagnostics
        )

    assert result is None
    assert "Flight Recorder write failed" in caplog.text
    assert diagnostics == {
        "invoked": True,
        "recorder_path": None,
        "before": {"exists": False, "size_bytes": None},
        "record_scan_succeeded": False,
        "exception": {
            "class": "OSError",
            "message": "[redacted: potentially sensitive exception message]",
        },
        "after": {"exists": False, "size_bytes": None},
    }
    assert "do-not-expose" not in repr(diagnostics)


def test_safe_record_scan_reports_append_and_download_reads_post_scan_bytes(tmp_path):
    path = tmp_path / "flights.jsonl"
    recorder = FlightRecorder(path)
    before_download = flight_recorder_download_bytes(recorder)
    diagnostics = {}

    result = record_scan_safely(
        recorder,
        seeds=[], discovery_reasons={}, snapshots={}, candidates=[], analyzed=[],
        records=[], settings=SETTINGS, runtime_diagnostics=diagnostics,
    )
    refreshed_download = flight_recorder_download_bytes(recorder)

    assert result is not None
    assert diagnostics["invoked"] is True
    assert diagnostics["recorder_path"] == str(path.resolve())
    assert diagnostics["before"] == {"exists": False, "size_bytes": None}
    assert diagnostics["record_scan_succeeded"] is True
    assert diagnostics["exception"] is None
    assert diagnostics["after"]["exists"] is True
    assert diagnostics["after"]["size_bytes"] > 0
    assert refreshed_download == path.read_bytes()
    assert len(refreshed_download) > len(before_download)


def test_hot_reload_repair_restores_scanner_package_reference(monkeypatch):
    import mide
    import mide.scanner_v2 as scanner_v2

    monkeypatch.delattr(mide, "scanner_v2", raising=False)

    repair_mide_module_links()

    assert mide.scanner_v2 is scanner_v2

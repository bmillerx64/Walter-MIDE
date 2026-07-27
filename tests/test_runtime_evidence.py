import json
from types import SimpleNamespace

from mide.flight_recorder import FlightRecorder
from mide.runtime_evidence import (
    current_scan_export,
    json_bytes,
    read_scans,
    runtime_file,
    symbol_history,
)

SETTINGS = SimpleNamespace(
    min_price=0.02, max_price=5.0, min_pct_change=5.0, min_day_volume=100_000
)


def snapshot():
    return {
        "latestTrade": {"p": 1.0},
        "latestQuote": {"bp": 0.99, "ap": 1.01},
        "dailyBar": {"c": 1.0, "v": 200_000},
        "prevDailyBar": {"c": 0.9},
    }


def record(state, score):
    return {
        "symbol": "DFNS",
        "status": state,
        "candidate_status": state,
        "qualified_for_watch": True,
        "qualified_for_entry": state == "Entry Ready",
        "qualified_for_alert": state == "Entry Ready",
        "qualified_for_ranking": True,
        "participation_score": 71,
        "participation_surge_score": 82,
        "volume_pace_ratio": 1.7,
        "acceleration_ratio": 1.3,
        "volume_acceleration": 1.2,
        "dollar_flow_acceleration": 1.1,
        "price": 1.0,
        "vwap_value": 0.98,
        "vwap_distance_pct": 2.04,
        "supertrend_bullish": True,
        "supertrend_flip_age": 3,
        "participation_gate": {"passed": True, "reason": "pass"},
        "structure_gate": {"passed": True, "reason": "pass"},
        "trigger_diagnostics": {"trigger": False, "checks": []},
        "opportunity_score": score,
        "conviction_score": 64,
        "source_bar_timestamp": "2026-07-27T14:30:00+00:00",
        "source_bar_age": 12,
    }


def scan(recorder, item, timestamp):
    original = dict(item)
    recorder.record_scan(
        seeds=["DFNS"],
        discovery_reasons={"DFNS": ["market mover"]},
        snapshots={"DFNS": snapshot()},
        candidates=[{"symbol": "DFNS"}],
        analyzed=[item],
        records=[item],
        settings=SETTINGS,
        timestamp=timestamp,
    )
    assert item == original  # evidence recording must not change scanner decisions


def test_multiple_scans_remain_exportable_in_chronological_order(tmp_path):
    recorder = FlightRecorder(tmp_path / "flight.jsonl")
    scan(
        recorder,
        record("Watching", 51),
        __import__("datetime").datetime(2026, 7, 27, 14, 32),
    )
    scan(
        recorder,
        record("Strengthening", 63),
        __import__("datetime").datetime(2026, 7, 27, 14, 31),
    )

    history = symbol_history(read_scans(recorder.path), "dfns")

    assert [item["opportunity_score"] for item in history] == [63, 51]
    assert history[0]["first_discovery"] is True
    assert history[1]["transition"] == "Strengthening -> Watching"


def test_current_scan_contains_required_diagnostics(tmp_path):
    recorder = FlightRecorder(tmp_path / "flight.jsonl")
    scan(
        recorder,
        record("Entry Ready", 88),
        __import__("datetime").datetime(2026, 7, 27, 14, 30),
    )
    exported = current_scan_export(recorder.latest_scan())["records"][0]
    required = {
        "symbol",
        "scan_timestamp",
        "discovery_status",
        "snapshot_prefilter_result",
        "snapshot_prefilter_rejection_reason",
        "workflow_state",
        "qualified_for_watch",
        "qualified_for_entry",
        "qualified_for_alert",
        "participation_score",
        "participation_surge_score",
        "vpi",
        "five_minute_vpi_acceleration",
        "legacy_volume_acceleration",
        "dollar_flow_acceleration",
        "price",
        "vwap",
        "vwap_distance",
        "supertrend_state",
        "supertrend_flip_age",
        "structure_gate",
        "participation_gate",
        "trigger_result",
        "trigger_failed_conditions",
        "opportunity_score",
        "conviction_score",
        "source_bar_timestamp",
        "source_bar_age",
    }
    assert required <= exported.keys()


def test_absent_runtime_file_has_clear_message(tmp_path):
    data, message = runtime_file(tmp_path / "missing.jsonl")
    assert data is None
    assert (
        message == f"Runtime file is absent: {(tmp_path / 'missing.jsonl').as_posix()}"
    )


def test_exports_remove_credentials_recursively():
    exported = json.loads(
        json_bytes(
            {
                "symbol": "SAFE",
                "ALPACA_API_KEY": "nope",
                "nested": {"authorization": "Bearer nope", "price": 1},
            }
        )
    )
    assert exported == {"nested": {"price": 1}, "symbol": "SAFE"}

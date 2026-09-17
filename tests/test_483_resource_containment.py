from __future__ import annotations

import json
from pathlib import Path

from mide.flight_recorder import FlightRecorder
from mide import gs483_resource_containment as gs483


def _scan(scan_id: str, symbol: str = "TEST") -> dict:
    return {
        "scan_id": scan_id,
        "timestamp": f"2026-09-17T20:0{scan_id[-1]}:00+00:00",
        "scanner_version": "V2",
        "symbols": [
            {
                "symbol": symbol,
                "stage_reached": "discovery",
                "events": [],
                "evidence": {"symbol": symbol},
            }
        ],
    }


def _write(path: Path, rows: list[dict], *, malformed_tail: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as handle:
        for row in rows:
            handle.write(json.dumps(row, separators=(",", ":")).encode("utf-8") + b"\n")
        if malformed_tail:
            handle.write(b'{"partial":')


def test_bounded_latest_scan_reads_tail_and_skips_malformed_trailing_row(tmp_path) -> None:
    path = tmp_path / "flight.jsonl"
    rows = [_scan("scan1"), _scan("scan2"), _scan("scan3")]
    _write(path, rows, malformed_tail=True)

    assert gs483.bounded_latest_scan(path, chunk_bytes=17)["scan_id"] == "scan3"


def test_streaming_scans_preserve_valid_order_without_path_read_text(tmp_path, monkeypatch) -> None:
    path = tmp_path / "flight.jsonl"
    rows = [_scan("scan1"), _scan("scan2"), _scan("scan3")]
    _write(path, rows)

    def forbidden(*args, **kwargs):
        raise AssertionError("whole-file read_text must not be used")

    monkeypatch.setattr(Path, "read_text", forbidden)
    assert [row["scan_id"] for row in gs483.streaming_scans(path)] == [
        "scan1",
        "scan2",
        "scan3",
    ]


def test_symbol_history_streams_without_materializing_all_scans(tmp_path, monkeypatch) -> None:
    path = tmp_path / "flight.jsonl"
    _write(path, [_scan("scan1", "AAA"), _scan("scan2", "BBB"), _scan("scan3", "AAA")])

    def forbidden(*args, **kwargs):
        raise AssertionError("FlightRecorder.scans must not be used")

    monkeypatch.setattr(FlightRecorder, "scans", forbidden)
    history = gs483.streaming_symbol_history(path, "aaa")
    assert [row["scan_id"] for row in history] == ["scan1", "scan3"]
    assert all(row["symbol"] == "AAA" for row in history)


def test_install_replaces_only_recorder_read_helpers(tmp_path, monkeypatch) -> None:
    gs483.install()
    recorder = FlightRecorder(tmp_path / "flight.jsonl")
    _write(recorder.path, [_scan("scan1"), _scan("scan2")])

    assert recorder.latest_scan()["scan_id"] == "scan2"
    assert [row["scan_id"] for row in recorder.scans()] == ["scan1", "scan2"]
    assert recorder.history_for_symbol("TEST")[-1]["scan_id"] == "scan2"
    assert getattr(FlightRecorder.latest_scan, "_gs483_resource_containment", False)
    assert getattr(FlightRecorder.scans, "_gs483_resource_containment", False)
    assert getattr(FlightRecorder.history_for_symbol, "_gs483_resource_containment", False)


def test_resource_snapshot_reads_metadata_only(tmp_path, monkeypatch) -> None:
    recorder = FlightRecorder(tmp_path / "flight.jsonl")
    _write(recorder.path, [_scan("scan1")])

    def forbidden(*args, **kwargs):
        raise AssertionError("resource diagnostics must not read recorder contents")

    monkeypatch.setattr(Path, "read_bytes", forbidden)
    monkeypatch.setattr(Path, "read_text", forbidden)
    snap = gs483.resource_snapshot(recorder)
    assert snap["authority"] == "RESOURCE_CONTAINMENT_ONLY"
    assert snap["flight_recorder_bytes"] == recorder.path.stat().st_size
    assert snap["trading_logic_changed"] is False


def test_gs483_scope_lock() -> None:
    source = Path("mide/gs483_resource_containment.py").read_text(encoding="utf-8")
    assert "qualified_for_entry" not in source
    assert "qualified_for_alert" not in source
    assert "ensure_stream" not in source
    assert "initialize_quotes" not in source
    assert "place_order" not in source
    assert "submit_order" not in source

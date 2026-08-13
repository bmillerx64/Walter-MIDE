"""Read-only replay API for persisted Walter Flight Recorder JSONL files."""

from __future__ import annotations

from mide.flight_replay import ReplayNotAvailable, replay_recorded_symbol


def replay_from_recorder(recorder, *, scan_id: str, symbol: str) -> dict:
    """Find a persisted scan by id and replay one symbol from frozen evidence."""
    for scan in recorder.scans():
        if scan.get("scan_id") == scan_id:
            return replay_recorded_symbol(scan, symbol)
    raise ReplayNotAvailable(f"scan {scan_id} was not found in the Flight Recorder")


def replay_latest_from_recorder(recorder, symbol: str) -> dict:
    """Replay the newest persisted occurrence of a symbol with immutable evidence."""
    symbol = str(symbol or "").strip().upper()
    for scan in reversed(recorder.scans()):
        path = next(
            (
                item for item in scan.get("symbols", [])
                if str(item.get("symbol") or "").upper() == symbol
            ),
            None,
        )
        if path and path.get("decision_time_evidence"):
            return replay_recorded_symbol(scan, symbol)
    raise ReplayNotAvailable(f"no replayable Flight Recorder evidence found for {symbol}")

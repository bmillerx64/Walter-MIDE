"""Single production write boundary for replayable Flight Recorder scans."""

from __future__ import annotations

import json

from mide.flight_recorder_persistence import prepare_replayable_paths


def persist_replayable_scan(recorder, scan: dict, records, *, data_mode=None) -> dict:
    """Enrich a completed scan and append it using the recorder's existing JSONL format."""
    replayable = dict(scan)
    replayable["symbols"] = prepare_replayable_paths(
        scan.get("symbols", []),
        records,
        scan_id=scan.get("scan_id"),
        scan_timestamp=scan.get("timestamp"),
        data_mode=data_mode,
    )
    with recorder.path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(replayable, default=str) + "\n")
    return replayable

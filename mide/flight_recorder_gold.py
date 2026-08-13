"""Gold Standard adapter for recording replayable Walter scans.

Kept separate from the production recorder so deployment can adopt the adapter
without altering Walter's live decision behavior.
"""

from __future__ import annotations

from mide.flight_recorder_evidence import attach_decision_time_evidence


def make_paths_replayable(paths, records, *, scan_id, scan_timestamp, data_mode=None):
    """Return recorder paths enriched with immutable evidence where records exist."""
    by_symbol = {str(r.get("symbol") or "").upper(): r for r in records}
    enriched = []
    for path in paths:
        symbol = str(path.get("symbol") or "").upper()
        enriched.append(
            attach_decision_time_evidence(
                path,
                by_symbol.get(symbol),
                scan_id=scan_id,
                scan_timestamp=scan_timestamp,
                data_mode=data_mode,
            )
        )
    return enriched

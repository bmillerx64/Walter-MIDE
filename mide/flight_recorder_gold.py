"""Gold Standard adapter for recording replayable Walter scans.

Kept separate from the production recorder so deployment can adopt the adapter
without altering Walter's live decision behavior.
"""

from __future__ import annotations

from copy import deepcopy

from mide.flight_recorder_evidence import attach_decision_time_evidence


def make_paths_replayable(paths, records, *, scan_id, scan_timestamp, data_mode=None):
    """Return recorder paths enriched with immutable evidence where records exist."""
    by_symbol = {str(r.get("symbol") or "").upper(): r for r in records}
    enriched = []
    for path in paths:
        symbol = str(path.get("symbol") or "").upper()
        record = by_symbol.get(symbol)
        replayable = attach_decision_time_evidence(
            path,
            record,
            scan_id=scan_id,
            scan_timestamp=scan_timestamp,
            data_mode=data_mode,
        )
        # GS422: persist GS421's observational maturation package instead of paying
        # its runtime cost and then dropping the result at the recorder projection.
        # Keep it outside decision-time authority: this remains calibration evidence.
        if isinstance(record, dict) and "multitimeframe_maturation" in record:
            replayable["multitimeframe_maturation"] = deepcopy(
                record.get("multitimeframe_maturation")
            )
            replayable["multitimeframe_maturation_authority"] = record.get(
                "multitimeframe_maturation_authority", "OBSERVATIONAL_ONLY"
            )
        enriched.append(replayable)
    return enriched

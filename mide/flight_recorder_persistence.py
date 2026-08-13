"""Gold Standard production persistence adapter for Flight Recorder replay evidence.

This module is deliberately tiny: it enriches recorder paths immediately before
persistence and does not participate in scoring, ranking, gates, alerts, or UI.
"""

from __future__ import annotations

from mide.flight_recorder_gold import make_paths_replayable


def prepare_replayable_paths(paths, records, *, scan_id, scan_timestamp, data_mode=None):
    """Return copied recorder paths with immutable evidence for analyzed records."""
    return make_paths_replayable(
        paths,
        records,
        scan_id=scan_id,
        scan_timestamp=scan_timestamp,
        data_mode=data_mode,
    )

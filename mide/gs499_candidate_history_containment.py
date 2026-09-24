"""GS499: keep Candidate History persistence bounded per scan record.

Sept. 18 live backup evidence showed Candidate History at about 939 MB after only
part of one market session. The file held 11,867 JSONL records averaging about
79 KB each, with individual rows reaching about 278 KB. The dominant growth was
not current market evidence; it was cumulative ledger history duplicated inside
every persisted row:

- architecture_audit grew by roughly eight entries per scan;
- ranking_history grew by one entry per scan;
- discovery_history grew by one entry per scan;
- reevaluation_history grew by one entry per scan.

Candidate History already stores one row per candidate observation, so embedding
the full prior lifetime again inside each new row creates super-linear file growth.
GS499 changes only the persistence projection. Live ledger records remain untouched
and retain their complete in-memory histories. Candidate History keeps the current
record plus only the bounded tail needed for local context.

No discovery, market data, scoring, ranking, gates, VWAP/ST truth, qualification,
readiness, alerting, execution, or orders are changed.
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any


_HISTORY_LIMITS = {
    "architecture_audit": 8,
    "ranking_history": 2,
    "discovery_history": 2,
    "reevaluation_history": 2,
}


def _replay_validation():
    from mide.authorities import replay_validation

    return replay_validation


def compact_candidate_history_record(record: Mapping[str, Any]) -> dict[str, Any]:
    """Warm-deploy-safe facade for bounded Candidate History persistence."""
    current = getattr(
        _replay_validation(),
        "compact_candidate_history_record",
        None,
    )
    if callable(current):
        return current(record)

    # Retained-runtime fallback for an older Replay / Validation generation.
    snapshot = dict(record)
    for field, limit in _HISTORY_LIMITS.items():
        value = record.get(field)
        if isinstance(value, list):
            snapshot[field] = list(value[-limit:])
    return snapshot

"""GS248 session-scoped history of completed-scan evidence readiness.

This module records the already-snapshotted GS247 readiness contract when a
completed scan is published. It is observability only: it never participates in
discovery, filtering, qualification, ranking, scoring, alerts, or execution.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping, MutableMapping


READINESS_HISTORY_KEY = "evidence_readiness_history"


def readiness_history_entry(scan: Any) -> dict[str, Any]:
    """Return a detached record of one completed scan's stored readiness snapshot."""
    diagnostics = getattr(scan, "diagnostics", {}) or {}
    snapshot = diagnostics.get("evidence_readiness")
    if not isinstance(snapshot, Mapping):
        snapshot = {}

    completed_at = getattr(scan, "completed_at", None)
    return {
        "completed_at": completed_at.isoformat() if completed_at is not None else None,
        "provider": getattr(scan, "provider", None),
        "source_label": getattr(scan, "source_label", ""),
        "readiness_snapshot": deepcopy(dict(snapshot)),
    }


def append_readiness_history(
    state: MutableMapping[str, Any], scan: Any
) -> list[dict[str, Any]]:
    """Append one detached readiness record for a newly published completed scan."""
    history = state.setdefault(READINESS_HISTORY_KEY, [])
    entry = readiness_history_entry(scan)

    # Publishing the same completed object more than once can occur during UI
    # reruns. Preserve one historical observation per completed scan timestamp.
    if history and history[-1].get("completed_at") == entry["completed_at"]:
        return history

    history.append(entry)
    return history


def readiness_history(state: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Return a detached copy of session readiness history for diagnostics use."""
    return deepcopy(list(state.get(READINESS_HISTORY_KEY, []) or []))

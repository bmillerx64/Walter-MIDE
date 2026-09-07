"""GS388: prune misleading diagnostic presentation without touching decisions.

This patch is deliberately presentation-only.  Walter's Flight Recorder schema
contains the authoritative key ``Participation Prefiltered`` while the Diagnostics
UI historically requested ``Prefiltered``.  That mismatch displayed a false zero
before a non-zero Analyzed count.  GS388 supplies a detached compatibility alias
when reading the latest scan so the existing UI shows the recorded value without
rewriting persisted evidence.

The patch does not alter discovery, market data, scoring, ranking, qualification,
readiness, thresholds, ST/VWAP, alerts, execution, candidate membership, or stored
Flight Recorder JSONL.
"""
from __future__ import annotations

from copy import deepcopy
from functools import wraps
from typing import Any


def display_safe_latest_scan(scan: dict[str, Any] | None) -> dict[str, Any] | None:
    """Return a detached latest-scan view with truthful legacy UI aliases."""
    if not isinstance(scan, dict):
        return scan
    output = deepcopy(scan)
    funnel = output.get("funnel")
    if isinstance(funnel, dict):
        # app.py's historical seven-metric panel asks for ``Prefiltered`` while
        # FlightRecorder correctly persists ``Participation Prefiltered``.
        # Preserve the authoritative key and add only the read-side alias.
        if "Prefiltered" not in funnel:
            funnel["Prefiltered"] = funnel.get("Participation Prefiltered", 0)
    return output


def install() -> None:
    """Install the detached Flight Recorder presentation compatibility view."""
    from .flight_recorder import FlightRecorder

    current = FlightRecorder.latest_scan
    if getattr(current, "_gs388_diagnostic_ui_pruning", False):
        return

    @wraps(current)
    def latest_scan(self):
        return display_safe_latest_scan(current(self))

    latest_scan._gs388_diagnostic_ui_pruning = True
    latest_scan._gs388_original = current
    FlightRecorder.latest_scan = latest_scan

"""Authoritative, session-scoped evidence from the last completed scan."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, MutableMapping


COMPLETED_SCAN_KEY = "completed_scan"


@dataclass(frozen=True)
class CompletedScan:
    """One atomic scan result shared by every post-scan dashboard view.

    The contained records, warnings, and diagnostics intentionally retain their
    identities.  Views must observe this object; they must not reconstruct a
    provider (or infer one from the currently selected control) when rendering.
    """

    provider: str | None
    records: list[dict[str, Any]]
    diagnostics: dict[str, Any]
    warnings: list[str]
    symbols_sampled: int
    prefilter_count: int
    completed_at: datetime
    source_label: str

    @property
    def pipeline_sources(self) -> list[dict[str, Any]]:
        return self.diagnostics.get("active_pipeline_sources", [])


def store_completed_scan(
    state: MutableMapping[str, Any], scan: CompletedScan
) -> CompletedScan:
    """Atomically publish a completed scan and its compatibility aliases."""
    state[COMPLETED_SCAN_KEY] = scan
    # These aliases remain for older UI helpers, but point into the same object.
    state["records"] = scan.records
    state["scan_diagnostics"] = scan.diagnostics
    state["api_warnings"] = scan.warnings
    state["symbols_sampled"] = scan.symbols_sampled
    state["prefilter_count"] = scan.prefilter_count
    state["last_updated"] = scan.completed_at
    state["source_label"] = scan.source_label
    return scan


def completed_scan_for_view(
    state: MutableMapping[str, Any], _view: str
) -> CompletedScan | None:
    """Return the single scan object used by every post-scan view."""
    scan = state.get(COMPLETED_SCAN_KEY)
    return scan if isinstance(scan, CompletedScan) else None

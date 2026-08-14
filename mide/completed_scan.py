"""Authoritative, session-scoped evidence from the last completed scan."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from typing import Any, MutableMapping
from mide.evidence_readiness import evidence_readiness_report
from mide.live_evidence_observation import live_evidence_observation

COMPLETED_SCAN_KEY = "completed_scan"
SCAN_CONTEXT_KEY = "scan_context"
_INFORMATIONAL_WARNING_PREFIXES = ("Skipped unsupported Webull snapshot symbol", "FMP free-float unavailable for", "Free-float refresh unresolved for")

@dataclass(frozen=True)
class CompletedScan:
    """One atomic scan result shared by every post-scan dashboard view."""
    provider: str | None
    records: list[dict[str, Any]]
    diagnostics: dict[str, Any]
    warnings: list[str]
    symbols_sampled: int
    prefilter_count: int
    completed_at: datetime
    source_label: str

    def __post_init__(self) -> None:
        notices, operational = [], []
        for warning in self.warnings:
            text = str(warning)
            (notices if text.startswith(_INFORMATIONAL_WARNING_PREFIXES) else operational).append(text)
        if notices:
            existing = list(self.diagnostics.get("data_quality_notices") or [])
            self.diagnostics["data_quality_notices"] = existing + notices

        observation = live_evidence_observation(self.records, scan_timestamp=self.completed_at)
        readiness = evidence_readiness_report(observation)
        # GS247 binds the readiness verdict to the exact evidence object rendered
        # by Diagnostics. This prevents presentation-time recomputation from
        # drifting away from the GS245 completed-scan snapshot.
        observation["readiness_snapshot"] = dict(readiness)
        self.diagnostics["live_evidence_observation"] = observation
        self.diagnostics["evidence_readiness"] = readiness
        object.__setattr__(self, "warnings", operational)

    @property
    def pipeline_sources(self) -> list[dict[str, Any]]:
        return self.diagnostics.get("active_pipeline_sources", [])

@dataclass
class ScanContext:
    completed_scan: CompletedScan | None = None
    provider_instance: Any = None
    pipeline: Any = None

def scan_context(state: MutableMapping[str, Any]) -> ScanContext:
    context = state.get(SCAN_CONTEXT_KEY)
    if all(hasattr(context, name) for name in ("completed_scan", "provider_instance", "pipeline")):
        return context
    legacy = state.get(COMPLETED_SCAN_KEY)
    context = ScanContext(completed_scan=legacy if legacy is not None else None)
    state[SCAN_CONTEXT_KEY] = context
    return context

def store_completed_scan(state: MutableMapping[str, Any], scan: CompletedScan) -> CompletedScan:
    context = scan_context(state)
    context.completed_scan = scan
    state[COMPLETED_SCAN_KEY] = scan
    return scan

def publish_scan_result(state: MutableMapping[str, Any], scan: CompletedScan) -> CompletedScan | None:
    if scan.diagnostics.get("scan_completed", True) is False or scan.symbols_sampled == 0:
        return completed_scan_for_view(state, "failed scan")
    return store_completed_scan(state, scan)

def completed_scan_for_view(state: MutableMapping[str, Any], _view: str) -> CompletedScan | None:
    return scan_context(state).completed_scan

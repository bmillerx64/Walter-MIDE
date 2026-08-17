"""Authoritative, session-scoped evidence from the last completed scan."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, MutableMapping

from mide.evidence_readiness import evidence_readiness_report
from mide.evidence_readiness_history import append_readiness_history
from mide.live_evidence_observation import live_evidence_observation


COMPLETED_SCAN_KEY = "completed_scan"
SCAN_CONTEXT_KEY = "scan_context"
LAST_SCAN_FAILURE_KEY = "last_scan_failure"

_INFORMATIONAL_WARNING_PREFIXES = (
    "Skipped unsupported Webull snapshot symbol",
    "FMP free-float unavailable for",
    "Free-float refresh unresolved for",
)


@dataclass(frozen=True)
class CompletedScan:
    """One atomic scan result shared by every post-scan dashboard view.

    Records and diagnostics retain the completed run's evidence. Benign symbol
    skips and fail-closed free-float coverage notices are preserved in
    ``diagnostics['data_quality_notices']`` instead of being mislabeled as API
    warnings in Data Validation.
    """

    provider: str | None
    records: list[dict[str, Any]]
    diagnostics: dict[str, Any]
    warnings: list[str]
    symbols_sampled: int
    prefilter_count: int
    completed_at: datetime
    source_label: str

    def __post_init__(self) -> None:
        notices = []
        operational = []
        for warning in self.warnings:
            text = str(warning)
            if text.startswith(_INFORMATIONAL_WARNING_PREFIXES):
                notices.append(text)
            else:
                operational.append(text)
        if notices:
            existing = list(self.diagnostics.get("data_quality_notices") or [])
            self.diagnostics["data_quality_notices"] = existing + notices

        # GS243 observes the already-completed candidate records. The report is
        # detached from those records and has no role in any scanner decision.
        observation = live_evidence_observation(
            self.records, scan_timestamp=self.completed_at
        )

        # GS245 snapshots the GS244 operator-readiness verdict beside the exact
        # completed-scan evidence that produced it. GS247 also binds that same
        # snapshot to the observation consumed by Diagnostics, preventing display
        # time recomputation while preserving the existing Diagnostics call site.
        readiness = evidence_readiness_report(observation)
        observation["readiness_snapshot"] = readiness
        self.diagnostics["live_evidence_observation"] = observation
        self.diagnostics["evidence_readiness"] = readiness
        object.__setattr__(self, "warnings", operational)

    @property
    def pipeline_sources(self) -> list[dict[str, Any]]:
        return self.diagnostics.get("active_pipeline_sources", [])


@dataclass
class ScanContext:
    """The sole session-scoped owner of Walter's live runtime.

    Streamlit executes ``app.py`` from top to bottom for every widget event and
    timer tick. Consequently no provider, pipeline, or result kept in an app
    local is durable. This object is placed in ``session_state`` once and owns
    both the reusable runtime objects and the last *successfully completed*
    immutable result.
    """

    completed_scan: CompletedScan | None = None
    provider_instance: Any = None
    pipeline: Any = None


def scan_context(state: MutableMapping[str, Any]) -> ScanContext:
    """Return the session's authoritative context, creating it only once."""
    context = state.get(SCAN_CONTEXT_KEY)
    if all(hasattr(context, name) for name in (
        "completed_scan", "provider_instance", "pipeline"
    )):
        return context
    legacy = state.get(COMPLETED_SCAN_KEY)
    context = ScanContext(completed_scan=legacy if legacy is not None else None)
    state[SCAN_CONTEXT_KEY] = context
    return context


def store_completed_scan(
    state: MutableMapping[str, Any], scan: CompletedScan
) -> CompletedScan:
    """Atomically publish a completed scan and its compatibility aliases."""
    context = scan_context(state)
    context.completed_scan = scan
    state[COMPLETED_SCAN_KEY] = scan
    state[LAST_SCAN_FAILURE_KEY] = None
    append_readiness_history(state, scan)
    return scan


def publish_scan_result(
    state: MutableMapping[str, Any], scan: CompletedScan
) -> CompletedScan | None:
    """Publish only a genuinely completed run, preserving prior evidence."""
    if (scan.diagnostics.get("scan_completed", True) is False
            or scan.symbols_sampled == 0):
        state[LAST_SCAN_FAILURE_KEY] = {
            "attempted_at": scan.completed_at,
            "message": (
                scan.warnings[-1] if scan.warnings
                else "The scan completed without a fresh symbol universe."
            ),
            "diagnostics": scan.diagnostics,
        }
        return completed_scan_for_view(state, "failed scan")
    return store_completed_scan(state, scan)


def record_scan_failure(
    state: MutableMapping[str, Any], *, message: str,
    attempted_at: datetime, diagnostics: dict[str, Any] | None = None,
) -> None:
    """Persist an attempt failure independently of the completed result."""
    state[LAST_SCAN_FAILURE_KEY] = {
        "attempted_at": attempted_at,
        "message": message,
        "diagnostics": diagnostics or {},
    }


def completed_scan_for_view(
    state: MutableMapping[str, Any], _view: str
) -> CompletedScan | None:
    """Return the single scan object used by every post-scan view."""
    return scan_context(state).completed_scan

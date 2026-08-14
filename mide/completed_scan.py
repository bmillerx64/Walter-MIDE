"""Authoritative, session-scoped evidence from the last completed scan."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, MutableMapping

from mide.live_evidence_observation import live_evidence_observation


COMPLETED_SCAN_KEY = "completed_scan"
SCAN_CONTEXT_KEY = "scan_context"

_INFORMATIONAL_WARNING_PREFIXES = (
    "Skipped unsupported Webull snapshot symbol",
    "FMP free-float unavailable for",
    "Free-float refresh unresolved for",
)


@dataclass(frozen=True)
class CompletedScan:
    """One atomic scan result shared by every post-scan dashboard view.

    Records and diagnostics retain the completed run's evidence.  Benign symbol
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
        # GS243 observes the already-completed candidate records.  The report is
        # detached from those records and has no role in any scanner decision.
        self.diagnostics["live_evidence_observation"] = live_evidence_observation(
            self.records, scan_timestamp=self.completed_at
        )
        object.__setattr__(self, "warnings", operational)

    @property
    def pipeline_sources(self) -> list[dict[str, Any]]:
        return self.diagnostics.get("active_pipeline_sources", [])


@dataclass
class ScanContext:
    """The sole session-scoped owner of Walter's live runtime.

    Streamlit executes ``app.py`` from top to bottom for every widget event and
    timer tick.  Consequently no provider, pipeline, or result kept in an app
    local is durable.  This object is placed in ``session_state`` once and owns
    both the reusable runtime objects and the last *successfully completed*
    immutable result.
    """

    completed_scan: CompletedScan | None = None
    provider_instance: Any = None
    pipeline: Any = None


def scan_context(state: MutableMapping[str, Any]) -> ScanContext:
    """Return the session's authoritative context, creating it only once.

    The small migration branch preserves a completed scan created by an older
    deployed app version during Streamlit hot reload.
    """
    context = state.get(SCAN_CONTEXT_KEY)
    # Streamlit may reload this module while retaining session_state.  An object
    # created by the previous class definition is still a valid context even
    # though ``isinstance`` would reject it after that reload.
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
    # One compatibility pointer supports a safe rolling deployment.  Derived
    # result fields are deliberately not copied into session_state: copying was
    # the second mutable runtime that could be reset independently on reruns.
    state[COMPLETED_SCAN_KEY] = scan
    return scan


def publish_scan_result(
    state: MutableMapping[str, Any], scan: CompletedScan
) -> CompletedScan | None:
    """Publish only a genuinely completed run, preserving prior evidence.

    The live pipeline's recovery boundary annotates an interrupted run with
    ``scan_completed=False``.  Such a run is not an empty-universe scan and must
    never replace the last completed result with misleading zero counts.
    """
    if (scan.diagnostics.get("scan_completed", True) is False
            or scan.symbols_sampled == 0):
        return completed_scan_for_view(state, "failed scan")
    return store_completed_scan(state, scan)


def completed_scan_for_view(
    state: MutableMapping[str, Any], _view: str
) -> CompletedScan | None:
    """Return the single scan object used by every post-scan view."""
    return scan_context(state).completed_scan

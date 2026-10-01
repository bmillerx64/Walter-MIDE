"""Authoritative evidence from the last completed scan.

The primary evidence contract remains session-scoped: every dashboard view in one
Streamlit session consumes one atomic ``CompletedScan``. GS412 adds a narrow
process-wide handoff for *live* completed scans. GS578 also gives the mutable live
provider one process-wide owner so a single browser tab that reconnects into a new
Streamlit session cannot create a second Webull runtime inside the same process.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
from datetime import datetime
import threading
from typing import Any, Callable, MutableMapping

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


# GS412 process-wide *completed evidence* handoff. The provider/pipeline remain
# session-owned; only an already-completed live result is shared. This prevents
# fresh/hot-reload browser sessions from each believing they owe an immediate
# scan and then ping-ponging the process watchdog a few seconds apart.
_PROCESS_LIVE_SCAN_LOCK = threading.RLock()
_PROCESS_LIVE_SCAN: CompletedScan | None = None

# GS578: Streamlit can replace a session after a websocket reconnect while the
# Python process remains alive. A session-owned provider then creates a second
# Webull SDK/runtime object even though the operator has only one browser tab.
# Keep exactly one mutable live provider per process and let each new
# ScanContext hold only an alias to that process owner. The process watchdog
# already serializes use of this provider, so sharing does not add concurrent
# scanner authority.
PROCESS_LIVE_PROVIDER_AUTHORITY = "PROCESS_WIDE_LIVE_PROVIDER_OWNER"
_PROCESS_LIVE_PROVIDER_LOCK = threading.RLock()
_PROCESS_LIVE_PROVIDER: Any = None
_PROCESS_LIVE_PROVIDER_IDENTITY: str | None = None
_PROCESS_LIVE_PROVIDER_CLAIMS = 0


def claim_process_live_provider(
    identity: str,
    current_provider: Any,
    factory: Callable[[], Any],
) -> tuple[Any, bool]:
    """Return the sole live provider for this Python process.

    ``current_provider`` lets a retained Streamlit session seed the owner if this
    module is refreshed independently. A genuinely fresh Streamlit session passes
    ``None`` and adopts the existing process provider instead of constructing a
    competing Webull SDK object. A changed identity intentionally creates a new
    owner so credential/provider changes never reuse an incompatible runtime.

    Returns ``(provider, created_now)``.
    """
    global _PROCESS_LIVE_PROVIDER
    global _PROCESS_LIVE_PROVIDER_IDENTITY
    global _PROCESS_LIVE_PROVIDER_CLAIMS

    normalized = str(identity or "").strip()
    if not normalized:
        raise ValueError("live provider identity is required")

    with _PROCESS_LIVE_PROVIDER_LOCK:
        created_now = False
        if (
            _PROCESS_LIVE_PROVIDER is not None
            and _PROCESS_LIVE_PROVIDER_IDENTITY == normalized
        ):
            provider = _PROCESS_LIVE_PROVIDER
        elif _PROCESS_LIVE_PROVIDER is None and current_provider is not None:
            provider = current_provider
            _PROCESS_LIVE_PROVIDER = provider
            _PROCESS_LIVE_PROVIDER_IDENTITY = normalized
        else:
            provider = factory()
            if provider is None:
                raise RuntimeError("live provider factory returned no provider")
            _PROCESS_LIVE_PROVIDER = provider
            _PROCESS_LIVE_PROVIDER_IDENTITY = normalized
            created_now = True

        _PROCESS_LIVE_PROVIDER_CLAIMS += 1
        diagnostics = getattr(provider, "diagnostics", None)
        if isinstance(diagnostics, dict):
            diagnostics["runtime_provider_owner"] = {
                "authority": PROCESS_LIVE_PROVIDER_AUTHORITY,
                "process_singleton": True,
                "identity": normalized,
                "claim_count": _PROCESS_LIVE_PROVIDER_CLAIMS,
                "created_on_this_claim": created_now,
                "session_state_is_alias_only": True,
                "scan_concurrency_authority_changed": False,
                "trading_authority_changed": False,
            }
        return provider, created_now


def process_live_provider() -> Any:
    """Return the process-owned live provider without claiming/replacing ownership."""
    with _PROCESS_LIVE_PROVIDER_LOCK:
        return _PROCESS_LIVE_PROVIDER


def _safe_copy_scan(scan: CompletedScan | None) -> CompletedScan | None:
    if scan is None:
        return None
    try:
        return copy.deepcopy(scan)
    except Exception:
        # Handoff is an operational convenience, never scan authority. If an
        # unexpected diagnostic object is not deepcopy-able, preserve the live
        # result rather than allowing the handoff itself to break publication.
        return scan


def _publish_process_live_scan(scan: CompletedScan) -> None:
    """Publish a completed live scan for other Streamlit sessions in this process."""
    if scan.provider is None:
        return
    global _PROCESS_LIVE_SCAN
    snapshot = _safe_copy_scan(scan)
    with _PROCESS_LIVE_SCAN_LOCK:
        _PROCESS_LIVE_SCAN = snapshot


def _process_live_scan_snapshot() -> CompletedScan | None:
    with _PROCESS_LIVE_SCAN_LOCK:
        return _safe_copy_scan(_PROCESS_LIVE_SCAN)


def process_live_scan_snapshot() -> CompletedScan | None:
    """Return detached last completed live evidence for awareness-only consumers."""
    return _process_live_scan_snapshot()


def _newer_process_live_scan_snapshot(
    local_epoch: float | None,
) -> CompletedScan | None:
    """Copy process evidence only when it can actually replace local evidence.

    GS602: completed_scan_for_view is called by several presentation wrappers on
    every Streamlit render. Deep-copying the complete process scan before checking
    its timestamp made every read pay for records + diagnostics even when the
    browser already held that exact scan. Hold the publication lock, compare the
    immutable completed_at first, and detach only a genuinely newer snapshot.
    """
    with _PROCESS_LIVE_SCAN_LOCK:
        process_epoch = _completed_epoch(_PROCESS_LIVE_SCAN)
        if process_epoch is None:
            return None
        if local_epoch is not None and local_epoch >= process_epoch:
            return None
        return _safe_copy_scan(_PROCESS_LIVE_SCAN)


def _state_wants_live_scan(state: MutableMapping[str, Any]) -> bool:
    mode = str(state.get("selected_data_mode") or "")
    provider = str(state.get("selected_live_provider") or "")
    return mode.startswith("Live ") or provider.upper() == "WEBULL"


def _completed_epoch(scan: CompletedScan | None) -> float | None:
    if scan is None:
        return None
    try:
        return float(scan.completed_at.timestamp())
    except (AttributeError, OSError, OverflowError, TypeError, ValueError):
        return None


def _adopt_newer_process_live_scan(
    state: MutableMapping[str, Any], context: ScanContext
) -> CompletedScan | None:
    """Adopt newer completed live evidence without sharing mutable session runtime.

    A scheduler-owned request carries no manual-request timestamp. When a fresher
    process result proves another session already completed the work, that stale
    automatic request is cleared so it cannot immediately seize the watchdog and
    start a duplicate scan. A manual request is never cleared here.
    """
    if not _state_wants_live_scan(state):
        return context.completed_scan

    local_epoch = _completed_epoch(context.completed_scan)
    process_scan = _newer_process_live_scan_snapshot(local_epoch)
    if process_scan is None:
        return context.completed_scan

    context.completed_scan = process_scan
    state[COMPLETED_SCAN_KEY] = process_scan
    state[LAST_SCAN_FAILURE_KEY] = None

    # Timed AutoScan sets only ``scan_requested``. Manual request_scan() also
    # writes ``_walter_scan_requested_epoch``; preserve that explicit intent.
    if (
        bool(state.get("scan_requested", False))
        and state.get("_walter_scan_requested_epoch") is None
    ):
        state["scan_requested"] = False

    return process_scan


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
    """Atomically publish a completed scan and its compatibility aliases.

    GS584 publishes the detached process-wide snapshot before exposing the same
    completed object through mutable Streamlit session state. Monday live logs
    captured a dictionary-size mutation error while overlapping Streamlit
    sessions were adopting/presenting a newly completed scan. Taking the process
    snapshot first removes that publication race without changing scan evidence
    or trading authority.
    """
    context = scan_context(state)
    _publish_process_live_scan(scan)
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
    """Return one completed result, adopting a fresher live process handoff if needed."""
    context = scan_context(state)
    return _adopt_newer_process_live_scan(state, context)

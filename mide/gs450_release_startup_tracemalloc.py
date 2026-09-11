"""GS450: do not leave tracemalloc active for Walter's entire trading session.

GS449 bounded the expensive full ``startup`` memory profile to once per Python process.
A second observability-cost issue remains inside the historical profiler itself: calling
``profile('startup', ...)`` starts ``tracemalloc`` but only stops it when the label starts
with ``scan``. The startup trace therefore remains active after the report is complete,
adding allocation bookkeeping to every later Streamlit rerun and live scan.

GS450 wraps the already-installed GS449 profile boundary. If startup profiling was not
already externally traced before the call, and the completed startup profile leaves
tracemalloc running, GS450 stops it immediately. Pre-existing external tracing is
preserved. Any later explicit ``scan ...`` profile can still start/stop tracing through
the historical memory profiler exactly as before.

Observability-cost containment only. No scheduler predicate, watchdog ownership,
provider request, market-data value, discovery, VWAP, SuperTrend, participation,
expansion, scoring, ranking, qualification, alert/audio, execution, or orders change.
"""
from __future__ import annotations

from functools import wraps
from typing import Any, Mapping


AUTHORITY = "OBSERVABILITY_COST_CONTAINMENT_ONLY"
_INSTALL_GENERATION = object()


def profile_and_release(
    current,
    memory_profile_module,
    label: str,
    *,
    session_state: Mapping[str, Any] | None = None,
    structures: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Release only tracing that Walter's startup profile itself turned on."""
    tracer = memory_profile_module.tracemalloc
    tracing_before = tracer.is_tracing()
    report = current(
        label,
        session_state=session_state,
        structures=structures,
    )
    if label == "startup" and not tracing_before and tracer.is_tracing():
        tracer.stop()
    return report


def install() -> None:
    """Install outside GS449 at the same early app startup boundary."""
    from . import memory_profile

    current = memory_profile.profile
    if getattr(current, "_gs450_install_generation", None) is _INSTALL_GENERATION:
        return

    @wraps(current)
    def profile(
        label: str,
        *,
        session_state: Mapping[str, Any] | None = None,
        structures: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        return profile_and_release(
            current,
            memory_profile,
            label,
            session_state=session_state,
            structures=structures,
        )

    profile._gs450_release_startup_tracemalloc = True
    profile._gs450_install_generation = _INSTALL_GENERATION
    profile._gs450_original = current
    profile._gs450_authority = AUTHORITY
    memory_profile.profile = profile

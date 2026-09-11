"""GS449: remove repeated full-memory profiling from AutoScan's pre-dispatch path.

Live validation after GS448 left a much smaller but highly regular cadence drift:
``first_due_observed_to_attempt_ms`` increased by about 118 ms per recurring scan.
The scheduler itself still observed the deadline promptly.

Static tracing of app.py found one explicitly O(process/session-size) operation before
``should_scan`` on *every* full-app rerun: ``memory_profile('startup', ...)``. The
legacy profile takes a tracemalloc snapshot, sorts allocation statistics, walks all
GC-tracked objects, recursively deep-sizes the full Streamlit session state and every
session key, then reads/writes a JSON report. Session diagnostic history grows with
completed scans, so repeating that work at every 60-second rerun creates exactly the
observed session-age slope.

GS449 preserves the full diagnostic profile once per Python process, then changes only
repeat ``startup`` calls to a constant-cost RSS observation. Explicit ``scan ...`` and
all other profile labels still execute the historical full profiler unchanged.

Observability-cost containment only. No scheduler predicate, watchdog ownership,
provider request, market-data value, discovery, VWAP, SuperTrend, participation,
expansion, scoring, ranking, qualification, alert/audio, execution, or orders change.
"""
from __future__ import annotations

from datetime import datetime, timezone
from functools import wraps
from typing import Any, Mapping


AUTHORITY = "OBSERVABILITY_COST_CONTAINMENT_ONLY"
_INSTALL_GENERATION = object()
_full_startup_profile_complete = False


def reset_for_tests() -> None:
    """Reset only GS449's process-local startup-profile sentinel."""
    global _full_startup_profile_complete
    _full_startup_profile_complete = False


def lightweight_startup_report(memory_profile_module) -> dict[str, Any]:
    """Return constant-cost repeat-startup diagnostics without object-graph walks."""
    return {
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "label": "startup",
        "rss_bytes": memory_profile_module.resident_memory_bytes(),
        "gs449_mode": "lightweight_repeat_startup",
        "gs449_authority": AUTHORITY,
        "full_profile_skipped": True,
        "trading_logic_changed": False,
    }


def bounded_profile(
    original,
    memory_profile_module,
    label: str,
    *,
    session_state: Mapping[str, Any] | None = None,
    structures: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Run one full startup profile per process; preserve every other profile call."""
    global _full_startup_profile_complete

    if label == "startup" and _full_startup_profile_complete:
        return lightweight_startup_report(memory_profile_module)

    report = original(
        label,
        session_state=session_state,
        structures=structures,
    )
    if label == "startup":
        _full_startup_profile_complete = True
    return report


def install() -> None:
    """Patch only the memory-profile callable app.py binds before sidebar rendering."""
    from . import memory_profile

    current = memory_profile.profile
    if getattr(current, "_gs449_install_generation", None) is _INSTALL_GENERATION:
        return

    @wraps(current)
    def profile(
        label: str,
        *,
        session_state: Mapping[str, Any] | None = None,
        structures: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        return bounded_profile(
            current,
            memory_profile,
            label,
            session_state=session_state,
            structures=structures,
        )

    profile._gs449_bound_startup_memory_profile = True
    profile._gs449_install_generation = _INSTALL_GENERATION
    profile._gs449_original = current
    profile._gs449_authority = AUTHORITY
    memory_profile.profile = profile

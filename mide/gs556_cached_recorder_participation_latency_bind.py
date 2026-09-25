"""GS556: bind GS554 Participation latency to the exact cached recorder instance.

GS555 correctly targeted the active recorder module graph, but live CAB evidence on
b2f5c7d5919c proved a warm Streamlit session can still persist through an older cached
FlightRecorder instance whose function globals are different from that module graph.

GS556 uses the same exact-instance discovery seam as GS487 and wraps that retained
persist_replayable_scan callable after GS487 has repaired the recorder. It copies only
the already-measured GS554 diagnostic into a top-level Flight Recorder field.

No provider call, timing recomputation, scan mutation outside diagnostics, or trading
authority change occurs here.
"""
from __future__ import annotations

from functools import wraps
from typing import Any


AUTHORITY = "OBSERVATIONAL_ONLY"
OWNER = "_walter_gs556_cached_recorder_participation_latency"
FIELD = "participation_latency_breakdown"


def install_for_recorder(recorder) -> bool:
    """Attach GS555 snapshot truth to the exact cached recorder persistence graph."""
    from mide import gs427_flight_recorder_latency_hard_bind as gs427
    from mide import gs487_cached_recorder_instance_bind as gs487
    from mide import gs555_participation_latency_hard_bind as gs555

    globals_dict = gs487._exact_recorder_globals(recorder)
    if not isinstance(globals_dict, dict):
        return False

    current = globals_dict.get("persist_replayable_scan")
    if not callable(current):
        return False
    if getattr(current, OWNER, False):
        return False

    @wraps(current)
    def persist_with_cached_participation_latency(
        recorder_obj,
        scan: dict,
        records,
        *args,
        **kwargs,
    ):
        provider, provider_source = gs427._active_provider()
        enriched = dict(scan or {})
        enriched[FIELD] = gs555.snapshot(provider, provider_source)
        return current(
            recorder_obj,
            enriched,
            records,
            *args,
            **kwargs,
        )

    setattr(persist_with_cached_participation_latency, OWNER, True)
    persist_with_cached_participation_latency._gs556_original = current
    globals_dict["persist_replayable_scan"] = (
        persist_with_cached_participation_latency
    )
    return True


__all__ = ["AUTHORITY", "OWNER", "FIELD", "install_for_recorder"]

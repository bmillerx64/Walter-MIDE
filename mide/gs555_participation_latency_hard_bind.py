"""GS555: overwrite-proof Flight Recorder bind for GS554 latency evidence.

The first live GS554 CAB proved that Participation timing was measured in app.py but
did not survive the retained recorder wrapper graph: latency_truth remained the
pre-GS554 shape on every current-build scan. GS555 writes the already-measured GS554
diagnostic as an independent top-level Flight Recorder field at the same hard app-entry
boundary used by GS486 transport truth.

No timing is recomputed here, no provider call is made, and no trading authority is
changed.
"""
from __future__ import annotations

from copy import deepcopy
from functools import wraps
from typing import Any


AUTHORITY = "OBSERVATIONAL_ONLY"
OWNER = "_walter_gs555_participation_latency_hard_bind"
FIELD = "participation_latency_breakdown"


def snapshot(provider, provider_source: str) -> dict[str, Any]:
    """Return the already-measured GS554 Participation timing snapshot."""
    from mide import gs554_participation_latency_breakdown as gs554

    diagnostics = getattr(provider, "diagnostics", None)
    payload = (
        deepcopy(diagnostics.get(gs554.DIAGNOSTIC_KEY) or {})
        if isinstance(diagnostics, dict)
        else {}
    )
    if not isinstance(payload, dict):
        payload = {}
    payload.setdefault("authority", AUTHORITY)
    payload["available"] = bool(payload)
    payload["provider_source"] = provider_source
    payload["gs555_hard_bind"] = True
    payload["extra_provider_calls"] = 0
    payload["market_data_values_changed"] = False
    payload["trading_logic_changed"] = False
    if not payload["available"]:
        payload.setdefault(
            "reason",
            "GS554 Participation latency diagnostics unavailable",
        )
    return payload


def install() -> bool:
    """Bind GS554 evidence to the exact retained Flight Recorder persistence graph."""
    from mide import flight_recorder
    from mide import gs427_flight_recorder_latency_hard_bind as gs427

    globals_dict = gs427._active_recorder_globals()
    current = globals_dict.get("persist_replayable_scan")
    if not callable(current):
        raise RuntimeError("Flight Recorder persistence callable is unavailable")
    if getattr(current, OWNER, False):
        return False

    @wraps(current)
    def persist_with_participation_latency(
        recorder,
        scan: dict,
        records,
        *args,
        **kwargs,
    ):
        provider, provider_source = gs427._active_provider()
        enriched = dict(scan or {})
        enriched[FIELD] = snapshot(provider, provider_source)
        return current(
            recorder,
            enriched,
            records,
            *args,
            **kwargs,
        )

    setattr(persist_with_participation_latency, OWNER, True)
    persist_with_participation_latency._gs555_original = current
    globals_dict["persist_replayable_scan"] = persist_with_participation_latency
    if globals_dict is flight_recorder.__dict__:
        flight_recorder.persist_replayable_scan = persist_with_participation_latency
    return True


__all__ = ["AUTHORITY", "OWNER", "FIELD", "snapshot", "install"]

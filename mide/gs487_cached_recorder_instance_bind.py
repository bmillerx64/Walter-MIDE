"""GS487: bind transport truth to the exact cached Flight Recorder instance.

FR #88 proved that Streamlit's cached ``FlightRecorder`` resource can outlive several
hot deployments.  GS484-GS486 patched newer module/class generations, while the object
actually writing JSONL rows could still execute a retained ``record_scan`` function.

GS487 does not guess which module generation is live.  Immediately before app.py calls
``recorder.record_scan(...)``, it starts from that exact cached object's bound method,
walks the retained wrapper chain, finds the base ``mide.flight_recorder`` globals used
by that method, and wraps *that dictionary's* ``persist_replayable_scan`` callable.

The wrapper persists only already-produced, credential-safe diagnostics: GS484 news
transport truth and GS481 Webull stream-failure truth.  It makes no provider request,
starts no stream, and changes no market-data, indicator, gate, score, alert, execution,
or order behavior.
"""
from __future__ import annotations

from functools import wraps
from typing import Any

AUTHORITY = "OBSERVATIONAL_ONLY"
BINDING = "cached_recorder.record_scan.__func__.__globals__.persist_replayable_scan"
REVISION = 1
_OWNER = "_walter_gs487_cached_recorder_instance_bind_revision"


def _exact_recorder_globals(recorder) -> dict[str, Any] | None:
    """Find the base globals dictionary used by this exact cached recorder object."""
    from . import gs427_flight_recorder_latency_hard_bind as gs427

    method = getattr(recorder, "record_scan", None)
    root = getattr(method, "__func__", method)
    if not callable(root):
        return None

    for function in gs427._walk_functions(root):
        globals_dict = getattr(function, "__globals__", None)
        if not isinstance(globals_dict, dict):
            continue
        if globals_dict.get("__name__") != "mide.flight_recorder":
            continue
        if callable(globals_dict.get("persist_replayable_scan")):
            return globals_dict
    return None


def _news_transport(provider, provider_source: str) -> dict[str, Any]:
    from . import gs484_fmp_transport_truth as gs484

    truth = dict(gs484.transport_truth(provider) or {})
    truth["provider_source"] = provider_source
    truth["cached_recorder_instance_bind"] = True
    truth["extra_provider_calls"] = 0
    truth["trading_authority_changed"] = False
    return truth


def _stream_transport(provider, provider_source: str) -> dict[str, Any]:
    from . import gs481_live_evidence_hard_bind as gs481

    truth = dict(gs481._stream_failure_truth(provider) or {})
    truth["provider_source"] = provider_source
    truth["cached_recorder_instance_bind"] = True
    truth["network_repair_attempted_here"] = False
    truth["trading_authority_changed"] = False
    return truth


def install_for_recorder(recorder) -> bool:
    """Wrap the persistence callable used by this exact cached recorder instance."""
    from . import gs427_flight_recorder_latency_hard_bind as gs427

    globals_dict = _exact_recorder_globals(recorder)
    if not isinstance(globals_dict, dict):
        return False

    current = globals_dict.get("persist_replayable_scan")
    if not callable(current):
        return False
    if getattr(current, _OWNER, None) == REVISION:
        return False

    @wraps(current)
    def persist_with_cached_instance_transport(recorder_obj, scan: dict, records, *args, **kwargs):
        provider, provider_source = gs427._active_provider()
        augmented = dict(scan)
        augmented["news_transport_trace"] = _news_transport(provider, provider_source)
        augmented["stream_transport_trace"] = _stream_transport(provider, provider_source)
        augmented["recorder_instance_transport_bind"] = {
            "authority": AUTHORITY,
            "binding": BINDING,
            "revision": REVISION,
            "provider_source": provider_source,
            "gs487_cached_recorder_instance_bind": True,
            "trading_authority_changed": False,
        }
        return current(recorder_obj, augmented, records, *args, **kwargs)

    setattr(persist_with_cached_instance_transport, _OWNER, REVISION)
    persist_with_cached_instance_transport._gs487_cached_recorder_instance_bind = True
    persist_with_cached_instance_transport._gs487_original = current
    globals_dict["persist_replayable_scan"] = persist_with_cached_instance_transport
    return True

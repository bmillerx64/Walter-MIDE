"""GS486: persist news and stream transport truth at an overwrite-proof scan boundary.

FR #87 proved two retained-runtime facts on build f3c791700220:
- GS480/GS481 story traces persisted, but GS484/GS485 transport enrichment still did not
  survive into ``news_story_trace``.
- genuine Webull 30-second streaming was healthy on the first new-build scan, then
  ``subscription_present=False`` / ``connection_status=error`` on every later scan,
  while the provider already retained the underlying exception in
  ``diagnostics['webull_stream']['subscription_failures']``.

GS486 stops trying to enrich a retained inner helper. Instead it wraps the active
``persist_replayable_scan`` global itself and adds two independent top-level keys
before calling the existing wrapper chain. Existing recorder wrappers preserve unknown
scan keys, so these transport traces survive old module generations by construction.

Observability only: zero provider calls, zero reconnects, zero news-selection changes,
and no discovery/indicator/score/rank/qualification/alert/execution/order authority.
"""
from __future__ import annotations

from functools import wraps
from typing import Any

AUTHORITY = "OBSERVATIONAL_ONLY"
_OWNER = "_walter_gs486_top_level_transport_truth_owner"


def _news_transport(provider, provider_source: str) -> dict[str, Any]:
    from . import gs484_fmp_transport_truth as gs484

    truth = dict(gs484.transport_truth(provider) or {})
    truth["provider_source"] = provider_source
    truth["top_level_hard_bind"] = True
    truth["extra_provider_calls"] = 0
    truth["trading_authority_changed"] = False
    return truth


def _stream_transport(provider, provider_source: str) -> dict[str, Any]:
    from . import gs481_live_evidence_hard_bind as gs481

    truth = dict(gs481._stream_failure_truth(provider) or {})
    truth["provider_source"] = provider_source
    truth["top_level_hard_bind"] = True
    truth["network_repair_attempted_here"] = False
    truth["trading_authority_changed"] = False
    return truth


def install() -> bool:
    """Wrap the exact active persistence global with overwrite-proof transport truth."""
    from . import flight_recorder
    from . import gs427_flight_recorder_latency_hard_bind as gs427

    globals_dict = gs427._active_recorder_globals()
    current = globals_dict.get("persist_replayable_scan")
    if not callable(current):
        raise RuntimeError("Flight Recorder persistence callable is unavailable")
    if getattr(current, _OWNER, False):
        return False

    @wraps(current)
    def persist_with_top_level_transport(recorder, scan: dict, records, *args, **kwargs):
        provider, provider_source = gs427._active_provider()
        augmented = dict(scan)
        augmented["news_transport_trace"] = _news_transport(provider, provider_source)
        augmented["stream_transport_trace"] = _stream_transport(provider, provider_source)
        augmented["transport_runtime_hard_bind"] = {
            "authority": AUTHORITY,
            "gs486_top_level_transport_truth": True,
            "provider_source": provider_source,
            "trading_authority_changed": False,
        }
        return current(recorder, augmented, records, *args, **kwargs)

    setattr(persist_with_top_level_transport, _OWNER, True)
    persist_with_top_level_transport._gs486_top_level_transport_truth = True
    persist_with_top_level_transport._gs486_original = current
    globals_dict["persist_replayable_scan"] = persist_with_top_level_transport
    if globals_dict is flight_recorder.__dict__:
        flight_recorder.persist_replayable_scan = persist_with_top_level_transport
    return True

"""GS481: hard-bind live news and Webull stream failure truth into Flight Recorder.

Fresh Sep. 17 Flight Recorder #82 proved two observability gaps on build 0b66121126bf:
GS480 was live but its story/publication trace never reached the retained recorder graph,
and the genuine 30-second Webull TICK stream had fallen to subscription_present=False /
connection_status=error without preserving the underlying subscription failure text.

GS481 changes observability only. It uses GS427's already-proven retained-recorder
binding to persist bounded GS480 news traces plus sanitized Webull stream-failure
context. It does not open/restart a stream, fetch extra news, alter market data,
indicators, scores, gates, qualification, alerts, execution or orders.
"""
from __future__ import annotations

from copy import deepcopy
from functools import wraps
import re
from typing import Any

AUTHORITY = "OBSERVATIONAL_ONLY"
_OWNER = "_walter_gs481_live_evidence_hard_bind_owner"
MAX_FAILURES = 3
MAX_TEXT = 300


def _sanitize(value: Any) -> str:
    text = " ".join(str(value or "").split())
    if re.search(
        r"(?i)authorization|bearer|credential|password|secret|token|api[-_ ]?key|headers?",
        text,
    ):
        return "[redacted: potentially sensitive stream failure]"
    return text[:MAX_TEXT]


def _json_safe(value: Any):
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    if hasattr(value, "isoformat"):
        try:
            return value.isoformat()
        except Exception:
            pass
    return str(value)[:MAX_TEXT]


def _news_truth() -> dict:
    from . import gs480_catalyst_story_intelligence as gs480

    marketwide = deepcopy(list(getattr(gs480, "_LATEST_MARKETWIDE_TRACE", []) or []))
    targeted = deepcopy(dict(getattr(gs480, "_LATEST_TARGETED_TRACE", {}) or {}))
    selected = deepcopy(list(getattr(gs480, "_LAST_SELECTED", []) or []))
    return {
        "authority": AUTHORITY,
        "gs480_story_pipeline_present": True,
        "marketwide": _json_safe(marketwide[-50:]),
        "targeted": _json_safe(targeted),
        "selected": _json_safe(selected[-50:]),
        "marketwide_count": len(marketwide),
        "targeted_count": len(targeted),
        "selected_count": len(selected),
        "extra_provider_calls": 0,
        "trading_authority_changed": False,
    }


def _stream_failure_truth(provider) -> dict:
    diagnostics = getattr(provider, "diagnostics", None)
    stream = diagnostics.get("webull_stream") if isinstance(diagnostics, dict) else None
    stream = stream if isinstance(stream, dict) else {}
    failures = list(stream.get("subscription_failures") or [])
    return {
        "authority": AUTHORITY,
        "connection_status": str(stream.get("stream_connection_status") or "unknown"),
        "subscription_present": getattr(provider, "_subscription", None) is not None if provider is not None else False,
        "subscribed_symbol_count": len(set(getattr(provider, "_subscribed", set()) or set())) if provider is not None else 0,
        "disconnect_count": int(stream.get("disconnect_count", 0) or 0),
        "stream_replaced_count": int(stream.get("stream_replaced_count", 0) or 0),
        "stream_cleanup_failures": int(stream.get("stream_cleanup_failures", 0) or 0),
        "subscription_failure_count": len(failures),
        "subscription_failures_tail": [_sanitize(item) for item in failures[-MAX_FAILURES:]],
        "stream_bypass_reason": _sanitize(stream.get("stream_bypass_reason")) if stream.get("stream_bypass_reason") else None,
        "network_repair_attempted_here": False,
        "trading_authority_changed": False,
    }


def _attach_stream_failure(scan: dict, provider) -> None:
    failure = _stream_failure_truth(provider)
    health = dict(scan.get("stream_30s_health") or {})
    health["failure_diagnostics"] = failure
    scan["stream_30s_health"] = health

    identity = dict(scan.get("recorder_runtime_identity") or {})
    nested = dict(identity.get("stream_30s_health") or {})
    nested["failure_diagnostics"] = failure
    identity["stream_30s_health"] = nested
    scan["recorder_runtime_identity"] = identity


def install() -> None:
    """Wrap the exact persistence callable used by the retained recorder graph."""
    from . import flight_recorder
    from . import gs427_flight_recorder_latency_hard_bind as gs427

    globals_dict = gs427._active_recorder_globals()
    current = globals_dict.get("persist_replayable_scan")
    if not callable(current):
        raise RuntimeError("Flight Recorder persistence callable is unavailable")
    if getattr(current, _OWNER, False):
        return

    @wraps(current)
    def persist_with_live_evidence(recorder, scan: dict, records, *args, **kwargs):
        provider, provider_source = gs427._active_provider()
        augmented = dict(scan)
        augmented["news_story_trace"] = _news_truth()
        augmented["live_evidence_hard_bind"] = {
            "authority": AUTHORITY,
            "provider_source": provider_source,
            "gs481_hard_bind": True,
            "trading_authority_changed": False,
        }
        _attach_stream_failure(augmented, provider)
        return current(recorder, augmented, records, *args, **kwargs)

    setattr(persist_with_live_evidence, _OWNER, True)
    persist_with_live_evidence._gs481_live_evidence_hard_bind = True
    persist_with_live_evidence._gs481_original = current
    globals_dict["persist_replayable_scan"] = persist_with_live_evidence
    if globals_dict is flight_recorder.__dict__:
        flight_recorder.persist_replayable_scan = persist_with_live_evidence

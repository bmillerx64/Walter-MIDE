"""GS389: retire the session Webull stream when Live Webull is deselected.

Ordinary Streamlit reruns intentionally keep one persistent LiveWebullProvider in
``ScanContext``. GS380 already retires an older process-local stream when another
production provider is constructed. One lifecycle gap remained: changing the
session from Live Webull to Demo does not construct a replacement provider, so the
old MQTT worker could remain connected even though the operator explicitly left
live mode.

GS389 closes only that session's existing subscription on an explicit mode change
away from Live Webull. The provider object and REST cache stay intact. If Live
Webull is selected again, the next live scan reuses the provider and opens a fresh
official SDK stream through the existing ``initialize_quotes -> ensure_stream``
path.

No discovery, scoring, ranking, readiness, qualification, thresholds, ST/VWAP,
alerts, execution, orders, or candidate membership are changed.
"""
from __future__ import annotations

from functools import wraps
from typing import Any, MutableMapping


def retire_session_stream_on_mode_exit(state: MutableMapping[str, Any]) -> bool:
    """Close a retained Webull stream iff the session explicitly left live mode."""
    from .session_controls import DATA_MODE_KEY
    from .completed_scan import SCAN_CONTEXT_KEY

    if str(state.get(DATA_MODE_KEY) or "") == "Live Webull":
        return False

    context = state.get(SCAN_CONTEXT_KEY)
    provider = getattr(context, "provider_instance", None)
    if provider is None:
        return False

    subscription = getattr(provider, "_subscription", None)
    if subscription is None:
        return False

    diagnostics = getattr(provider, "diagnostics", None)
    stream = diagnostics.setdefault("webull_stream", {}) if isinstance(diagnostics, dict) else {}
    try:
        subscription.close()
    except Exception as exc:
        stream["stream_cleanup_failures"] = int(stream.get("stream_cleanup_failures", 0) or 0) + 1
        stream["stream_mode_exit_error"] = type(exc).__name__
        return False
    finally:
        # Even if close raises, the failed transport is no longer authoritative.
        provider._subscription = None
        subscribed = getattr(provider, "_subscribed", None)
        if hasattr(subscribed, "clear"):
            subscribed.clear()
        if stream:
            stream["subscribed_symbols"] = 0
            stream["stream_connection_status"] = "bypassed"
            stream["stream_bypass_reason"] = "Live Webull mode is not selected"
            stream["stream_mode_exit_count"] = int(stream.get("stream_mode_exit_count", 0) or 0) + 1
    return True


def install() -> None:
    """Wrap only the explicit data-mode callback; ordinary reruns are untouched."""
    from . import session_controls

    current = session_controls.select_data_mode
    if getattr(current, "_gs389_webull_mode_exit_lifecycle", False):
        return

    @wraps(current)
    def select_data_mode(state):
        current(state)
        retire_session_stream_on_mode_exit(state)

    select_data_mode._gs389_webull_mode_exit_lifecycle = True
    select_data_mode._gs389_original = current
    session_controls.select_data_mode = select_data_mode

"""GS490: prevent new Webull TICK connections outside 04:00-20:00 ET.

FR #93 closed the rc105/backoff validation but exposed one remaining lifecycle gap:
GS469 correctly refuses to *force* stale-stream reconnects outside Webull's extended
U.S. equity window, while LiveWebullProvider.initialize_quotes still calls the normal
ensure_stream path whenever no subscription exists. A missing/dead subscription could
therefore initiate a brand-new MQTT connection after 20:00 ET even though Walter has
no overnight quote entitlement.

GS490 guards only stream initiation. If no live subscription exists and Eastern time
is outside weekday 04:00 <= t < 20:00, ensure_stream returns without opening a new
TICK connection. REST snapshots, history, news and the rest of the scan continue.
At or after 04:00 ET on the next weekday, the normal GS489/GS469 stream path is allowed
again. An already-live subscription is not retired or otherwise modified here.

No discovery, market-data values, synthetic 30s data, indicators, VWAP/ST formulas,
scores, gates, ranking, qualification, alerts, execution or orders are changed.
"""
from __future__ import annotations

from datetime import datetime, time, timezone
from functools import wraps
from typing import Callable

AUTHORITY = "WEBULL_TICK_INITIATION_WINDOW"
STREAM_START_ET = time(4, 0)
STREAM_END_ET = time(20, 0)
BYPASS_REASON = "Outside Webull 04:00-20:00 ET TICK initiation window"
_OWNER = "_walter_gs490_stream_window_guard"
REVISION = 1


def _utc(value: datetime | None = None) -> datetime:
    if value is None:
        return datetime.now(timezone.utc)
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def stream_window_open(value: datetime | None = None) -> bool:
    """Return whether a new U.S. equity TICK connection may be initiated."""
    from .time_service import eastern_time

    current = eastern_time(_utc(value))
    clock = current.time().replace(tzinfo=None)
    return current.weekday() < 5 and STREAM_START_ET <= clock < STREAM_END_ET


def _stream(provider) -> dict:
    diagnostics = getattr(provider, "diagnostics", None)
    if not isinstance(diagnostics, dict):
        diagnostics = {}
        try:
            provider.diagnostics = diagnostics
        except Exception:
            return {}
    stream = diagnostics.get("webull_stream")
    if not isinstance(stream, dict):
        stream = {}
        diagnostics["webull_stream"] = stream
    return stream


def ensure_stream_in_window(
    original: Callable,
    provider,
    symbols,
    *,
    now: datetime | None = None,
):
    """Block only creation of a new TICK subscription outside the allowed window."""
    stream = _stream(provider)
    existing = getattr(provider, "_subscription", None) is not None
    allowed = stream_window_open(now)
    state = stream.get("gs490_stream_window_guard")
    if not isinstance(state, dict):
        state = {
            "authority": AUTHORITY,
            "blocked_new_connection_attempts": 0,
            "trading_authority_changed": False,
            "rest_snapshot_history_unchanged": True,
            "genuine_webull_tick_only": True,
        }
        stream["gs490_stream_window_guard"] = state
    state.update(
        window_open=allowed,
        subscription_present=existing,
        stream_start_et="04:00",
        stream_end_et="20:00",
        weekdays_only=True,
    )

    if not existing and not allowed:
        state["blocked_new_connection_attempts"] = int(
            state.get("blocked_new_connection_attempts", 0) or 0
        ) + 1
        state["blocked_last_check"] = True
        stream["stream_connection_status"] = "bypassed"
        stream["stream_bypass_reason"] = BYPASS_REASON
        return False

    state["blocked_last_check"] = False
    if stream.get("stream_bypass_reason") == BYPASS_REASON:
        stream["stream_bypass_reason"] = None
        if stream.get("stream_connection_status") == "bypassed":
            stream["stream_connection_status"] = "disconnected"
    return original(symbols)


def install_for_provider(provider) -> bool:
    """Wrap the exact retained provider used by the current Streamlit session."""
    if provider is None:
        return False
    current = getattr(provider, "ensure_stream", None)
    if not callable(current):
        return False
    function = getattr(current, "__func__", current)
    if getattr(function, _OWNER, None) == REVISION or getattr(current, _OWNER, None) == REVISION:
        return False

    @wraps(current)
    def guarded(symbols):
        return ensure_stream_in_window(current, provider, symbols)

    setattr(guarded, _OWNER, REVISION)
    guarded._gs490_original = current
    try:
        provider.ensure_stream = guarded
    except (AttributeError, TypeError):
        return False
    return True

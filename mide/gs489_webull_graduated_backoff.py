"""GS489: graduate repeated Webull rc105 connection-limit retries.

FR #92 showed that GS488 correctly stopped per-scan reconnect hammering, but Webull
continued returning rc105 after five-minute cooldowns at roughly 22:30, 22:36 and
22:41 UTC. A fixed five-minute probe is therefore still too aggressive for a remote
account/session slot that is not clearing promptly.

GS489 keeps GS488's narrow scope and changes only rc105 retry cadence:
5 minutes after the first limit rejection, 10 minutes after the second, then a
15-minute cap for the third and later consecutive rejections. A successful live
subscription resets the sequence immediately.

Warm Streamlit sessions may retain the exact pre-GS489 provider and GS488 wrapper.
The app therefore imports this uniquely named module before each Live Webull snapshot
cycle and install_for_provider replaces only the helper referenced by that retained
wrapper's globals. It does not nest a second retry wrapper or double-count failures.

REST snapshots/history, genuine Webull TICK-only 30s truth, discovery, indicators,
VWAP/ST, scoring, gates, ranking, qualification, alerts, execution and orders are
unchanged.
"""
from __future__ import annotations

from functools import wraps
import time
from typing import Any, Callable

AUTHORITY = "WEBULL_CONNECTION_LIMIT_GRADUATED_BACKOFF"
BACKOFF_SECONDS = (300.0, 600.0, 900.0)
_STATE_KEY = "gs488_connection_limit_backoff"
_GS488_OWNER = "_walter_gs488_connection_limit_backoff"
_GS489_OWNER = "_walter_gs489_graduated_backoff_revision"
REVISION = 1


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


def _state(provider) -> dict:
    stream = _stream(provider)
    state = stream.get(_STATE_KEY)
    if not isinstance(state, dict):
        state = {
            "authority": "WEBULL_CONNECTION_LIMIT_CONTAINMENT",
            "active": False,
            "cooldown_seconds": BACKOFF_SECONDS[0],
            "next_retry_epoch": None,
            "consecutive_limit_failures": 0,
            "suppressed_attempts": 0,
            "last_limit_failure": None,
            "rest_snapshot_history_unchanged": True,
            "genuine_webull_tick_only": True,
            "trading_authority_changed": False,
        }
        stream[_STATE_KEY] = state
    state["backoff_schedule_seconds"] = list(BACKOFF_SECONDS)
    state["gs489_graduated_backoff"] = True
    state["gs489_authority"] = AUTHORITY
    return state


def _is_connection_limit(value: Any) -> bool:
    text = " ".join(str(value or "").split()).casefold()
    return "connection limit exceeded" in text or (
        "rc code: 105" in text and "limit" in text
    )


def _cooldown_for_failures(value: Any) -> float:
    try:
        failures = max(1, int(value))
    except (TypeError, ValueError):
        failures = 1
    return BACKOFF_SECONDS[min(failures - 1, len(BACKOFF_SECONDS) - 1)]


def _refresh_active_deadline(provider, *, now: float) -> dict:
    """Migrate a retained fixed GS488 deadline without allowing an earlier retry."""
    state = _state(provider)
    if not state.get("active") or getattr(provider, "_subscription", None) is not None:
        return state
    try:
        failures = int(state.get("consecutive_limit_failures", 0) or 0)
    except (TypeError, ValueError):
        failures = 0
    if failures <= 0:
        return state
    cooldown = _cooldown_for_failures(failures)
    try:
        last_failure = float(state.get("last_limit_failure_epoch"))
    except (TypeError, ValueError):
        last_failure = now
    desired_deadline = last_failure + cooldown
    try:
        current_deadline = float(state.get("next_retry_epoch"))
    except (TypeError, ValueError):
        current_deadline = 0.0
    state["cooldown_seconds"] = cooldown
    if desired_deadline > current_deadline:
        state["next_retry_epoch"] = desired_deadline
        state["gs489_retained_deadline_extended"] = True
    return state


def ensure_stream_with_graduated_backoff(
    original: Callable,
    provider,
    symbols,
    *,
    now: float | None = None,
):
    """Delegate once unless the explicit rc105 graduated cooldown is active."""
    current = float(time.time() if now is None else now)
    state = _refresh_active_deadline(provider, now=current)

    if getattr(provider, "_subscription", None) is not None:
        result = original(symbols)
        if result:
            state["active"] = False
            state["next_retry_epoch"] = None
            state["consecutive_limit_failures"] = 0
            state["cooldown_seconds"] = BACKOFF_SECONDS[0]
            state["last_recovery_epoch"] = current
        return result

    try:
        deadline = float(state.get("next_retry_epoch"))
    except (TypeError, ValueError):
        deadline = 0.0
    if state.get("active") and deadline > current:
        state["suppressed_attempts"] = int(state.get("suppressed_attempts", 0) or 0) + 1
        state["last_suppressed_epoch"] = current
        return False

    stream = _stream(provider)
    before = len(list(stream.get("subscription_failures") or []))
    result = original(symbols)
    failures = list(stream.get("subscription_failures") or [])
    newest = failures[-1] if len(failures) > before else None

    if result:
        state["active"] = False
        state["next_retry_epoch"] = None
        state["consecutive_limit_failures"] = 0
        state["cooldown_seconds"] = BACKOFF_SECONDS[0]
        state["last_recovery_epoch"] = current
        return result

    if _is_connection_limit(newest):
        count = int(state.get("consecutive_limit_failures", 0) or 0) + 1
        cooldown = _cooldown_for_failures(count)
        state["active"] = True
        state["cooldown_seconds"] = cooldown
        state["next_retry_epoch"] = current + cooldown
        state["consecutive_limit_failures"] = count
        state["last_limit_failure"] = "WEBULL_RC105_CONNECTION_LIMIT"
        state["last_limit_failure_epoch"] = current
    else:
        state["active"] = False
        state["next_retry_epoch"] = None
    return result


def install_for_provider(provider) -> bool:
    """Upgrade the exact retained provider without nesting another GS488 wrapper."""
    if provider is None:
        return False
    current = getattr(provider, "ensure_stream", None)
    if not callable(current):
        return False
    function = getattr(current, "__func__", current)

    if getattr(function, _GS489_OWNER, None) == REVISION:
        _refresh_active_deadline(provider, now=time.time())
        return False

    if getattr(function, _GS488_OWNER, False):
        globals_dict = getattr(function, "__globals__", None)
        if not isinstance(globals_dict, dict) or "ensure_stream_with_backoff" not in globals_dict:
            return False
        globals_dict["ensure_stream_with_backoff"] = ensure_stream_with_graduated_backoff
        setattr(function, _GS489_OWNER, REVISION)
        _refresh_active_deadline(provider, now=time.time())
        return True

    @wraps(current)
    def guarded(symbols):
        return ensure_stream_with_graduated_backoff(current, provider, symbols)

    setattr(guarded, _GS489_OWNER, REVISION)
    guarded._gs489_original = current
    try:
        provider.ensure_stream = guarded
    except (AttributeError, TypeError):
        return False
    _refresh_active_deadline(provider, now=time.time())
    return True

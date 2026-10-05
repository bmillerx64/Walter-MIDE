"""GS637: bounded recovery for Webull MQTT INVALID_SESSION.

Monday 2026-10-05 live evidence proved the canonical REST AutoScan could remain
healthy while the optional Webull TICK lane failed with:

    HTTP Status: 417, Code: INVALID_SESSION,
    Msg: Mqtt connection not exist for session: ...

GS627 Live Ignition Watch intentionally makes no network calls, so a dead TICK
transport leaves LIW without fresh cached price/30-second evidence even while the
60-second scanner continues normally.

GS637 is deliberately narrow:
- recognize only the observed MQTT INVALID_SESSION signature;
- reuse the exact process-owned provider and existing GS469/GS489/GS490/GS629
  reconnect/membership chain;
- retire any partially retained subscription, then allow exactly one immediate
  retry through that already-installed chain;
- never create another provider, scheduler, scan, or authority path;
- retain REST snapshot/history fallback when recovery fails.

No discovery, ranking, thresholds, Walter state, Entry authority, LIW thresholds,
audio authority, execution, or orders are changed.
"""

from __future__ import annotations

from datetime import datetime, timezone
from functools import wraps
from typing import Callable, Iterable


AUTHORITY = "WEBULL_MQTT_INVALID_SESSION_RECOVERY"
_OWNER = "_walter_gs637_invalid_session_recovery"
REVISION = 1


def _symbols(values: Iterable[str]) -> list[str]:
    return list(
        dict.fromkeys(
            str(value or "").strip().upper()
            for value in values or []
            if str(value or "").strip()
        )
    )


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


def _invalid_session_failure(value) -> bool:
    """Match only the confirmed Webull MQTT session-registration failure."""
    text = " ".join(str(value or "").split()).casefold()
    return (
        "invalid_session" in text
        and "mqtt connection not exist for session" in text
    )


def _trace(provider) -> dict:
    stream = _stream(provider)
    trace = stream.get("gs637_invalid_session_recovery")
    if not isinstance(trace, dict):
        trace = {
            "authority": AUTHORITY,
            "detected_total": 0,
            "recovery_attempts": 0,
            "recovery_successes": 0,
            "recovery_failures": 0,
            "last_detected_at": None,
            "last_failure": None,
            "last_retry_result": None,
            "last_tick_timestamp_ms": None,
            "tick_messages_received": 0,
            "one_retry_only": True,
            "process_provider_reused": True,
            "second_provider_created": False,
            "second_scheduler_created": False,
            "rest_snapshot_history_unchanged": True,
            "liw_thresholds_changed": False,
            "trading_authority_changed": False,
            "audio_authority_changed": False,
            "execution_authority_changed": False,
        }
        stream["gs637_invalid_session_recovery"] = trace
    return trace


def _refresh_tick_truth(provider, trace: dict) -> None:
    stream = _stream(provider)
    trace["last_tick_timestamp_ms"] = stream.get("last_tick_timestamp_ms")
    try:
        trace["tick_messages_received"] = int(
            stream.get("tick_messages_received") or 0
        )
    except (TypeError, ValueError):
        trace["tick_messages_received"] = 0
    trace["stream_connection_status"] = stream.get("stream_connection_status")


def ensure_stream_with_invalid_session_recovery(
    original: Callable,
    provider,
    symbols: Iterable[str],
):
    """Delegate normally, then make one bounded retry for a fresh INVALID_SESSION."""
    requested = _symbols(symbols)
    stream = _stream(provider)
    trace = _trace(provider)
    _refresh_tick_truth(provider, trace)

    failures_before = len(list(stream.get("subscription_failures") or []))
    result = original(requested)
    failures_after = list(stream.get("subscription_failures") or [])
    _refresh_tick_truth(provider, trace)
    trace["last_result"] = bool(result)

    if result:
        trace["last_retry_result"] = True if trace.get("last_retry_result") else None
        return result

    newest = (
        failures_after[-1]
        if len(failures_after) > failures_before
        else None
    )
    if not _invalid_session_failure(newest):
        return result

    trace["detected_total"] = int(trace.get("detected_total") or 0) + 1
    trace["last_detected_at"] = datetime.now(timezone.utc).isoformat()
    trace["last_failure"] = str(newest)
    trace["recovery_attempts"] = int(trace.get("recovery_attempts") or 0) + 1

    # Recycle only the exact process-owned stream object. The existing provider,
    # scan scheduler, REST clients, state machine, and GS627 observer stay intact.
    try:
        from mide import gs379_webull_stream_data_truth as gs379

        gs379._retire_provider_stream(provider)
        trace["dead_subscription_retired"] = True
    except Exception as exc:
        trace["dead_subscription_retired"] = False
        trace["retire_error_type"] = type(exc).__name__

    retry_failures_before = len(
        list(stream.get("subscription_failures") or [])
    )
    retry_result = original(requested)
    retry_failures_after = list(stream.get("subscription_failures") or [])
    _refresh_tick_truth(provider, trace)
    trace["last_retry_result"] = bool(retry_result)

    if retry_result:
        trace["recovery_successes"] = int(
            trace.get("recovery_successes") or 0
        ) + 1
        trace["last_retry_failure"] = None
    else:
        trace["recovery_failures"] = int(
            trace.get("recovery_failures") or 0
        ) + 1
        trace["last_retry_failure"] = (
            retry_failures_after[-1]
            if len(retry_failures_after) > retry_failures_before
            else None
        )

    # Never recurse or perform a third connection attempt here. If the one fresh
    # transport does not recover, existing GS469 remains the sole later retry owner.
    return retry_result


def install_for_provider(provider) -> bool:
    """Install outside the existing stream guard chain on one retained provider."""
    if provider is None:
        return False
    current = getattr(provider, "ensure_stream", None)
    if not callable(current):
        return False
    function = getattr(current, "__func__", current)
    if (
        getattr(function, _OWNER, None) == REVISION
        or getattr(current, _OWNER, None) == REVISION
    ):
        return False

    @wraps(current)
    def guarded(symbols):
        return ensure_stream_with_invalid_session_recovery(
            current,
            provider,
            symbols,
        )

    setattr(guarded, _OWNER, REVISION)
    guarded._gs637_original = current
    try:
        provider.ensure_stream = guarded
    except (AttributeError, TypeError):
        return False
    return True


__all__ = [
    "AUTHORITY",
    "REVISION",
    "ensure_stream_with_invalid_session_recovery",
    "install_for_provider",
]

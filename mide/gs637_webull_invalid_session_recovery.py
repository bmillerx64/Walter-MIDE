"""GS637: bounded recovery for Webull MQTT INVALID_SESSION.

Monday 2026-10-05 live evidence proved the canonical REST AutoScan could remain
healthy while the optional Webull TICK lane failed with:

    HTTP Status: 417, Code: INVALID_SESSION,
    Msg: Mqtt connection not exist for session: ...

GS627 Live Ignition Watch intentionally makes no network calls, so a dead TICK
transport leaves LIW without fresh cached price/30-second evidence even while the
60-second scanner continues normally.

The observed failure occurs at the SDK HTTP subscribe step immediately after MQTT
connect. GS637 therefore gives that exact connected MQTT transport one short,
bounded re-subscribe attempt before retiring it. It does not open a second provider,
second scheduler, or parallel reconnect owner. If the retry fails, the transport is
closed and Walter's existing GS469 lifecycle remains the sole later reconnect owner.

No discovery, ranking, thresholds, Walter state, Entry authority, LIW thresholds,
audio authority, execution, or orders are changed.
"""

from __future__ import annotations

from datetime import datetime, timezone
from functools import wraps
import time
from typing import Iterable


AUTHORITY = "WEBULL_MQTT_INVALID_SESSION_RECOVERY"
_OWNER = "_walter_gs637_invalid_session_recovery"
_TRANSPORT_OWNER = "_walter_gs637_transport_subscribe"
REVISION = 2
INVALID_SESSION_RETRY_DELAY_SECONDS = 0.75


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
            "same_transport_retry_attempts": 0,
            "same_transport_retry_successes": 0,
            "terminal_invalid_session_failures": 0,
            "last_detected_at": None,
            "last_failure": None,
            "last_retry_result": None,
            "last_tick_timestamp_ms": None,
            "tick_messages_received": 0,
            "retry_delay_seconds": INVALID_SESSION_RETRY_DELAY_SECONDS,
            "one_retry_only": True,
            "same_mqtt_transport_retry": True,
            "process_provider_reused": True,
            "second_provider_created": False,
            "second_scheduler_created": False,
            "gs469_remains_reconnect_owner": True,
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


def _install_transport_patch() -> bool:
    """Patch only GS379's SDK TICK subscribe seam; never create a connection."""
    from mide import gs379_webull_stream_data_truth as gs379

    owner = gs379.OfficialWebullTickTransport
    current = owner.subscribe
    if getattr(current, _TRANSPORT_OWNER, None) == REVISION:
        return False

    @wraps(current)
    def subscribe(self, symbols) -> None:
        wanted = self._symbols(symbols)
        if not wanted:
            return

        self._subscribed.clear()
        recovered_event = None
        try:
            self.client.subscribe(wanted, "US_STOCK", ["TICK"])
            if not self._subscribed.wait(gs379.SUBSCRIBE_TIMEOUT_SECONDS):
                raise RuntimeError(
                    "Webull OpenAPI tick subscription did not confirm"
                )
            return
        except BaseException as first_exc:
            if not _invalid_session_failure(first_exc):
                self.close()
                raise

            recovered_event = {
                "detected_at": datetime.now(timezone.utc).isoformat(),
                "first_failure": str(first_exc),
                "retry_attempted": True,
                "retry_result": False,
                "consumed": False,
            }
            self._gs637_recovery_event = recovered_event

            # The MQTT connection callback has already fired. The failure is the
            # Webull HTTP subscription registry not yet recognizing that session.
            # Keep the same transport alive briefly and retry only that HTTP
            # subscription once; do not create another MQTT connection here.
            time.sleep(INVALID_SESSION_RETRY_DELAY_SECONDS)
            self._subscribed.clear()
            try:
                self.client.subscribe(wanted, "US_STOCK", ["TICK"])
                if not self._subscribed.wait(gs379.SUBSCRIBE_TIMEOUT_SECONDS):
                    raise RuntimeError(
                        "Webull OpenAPI tick subscription did not confirm "
                        "after INVALID_SESSION retry"
                    )
            except BaseException:
                self.close()
                raise

            recovered_event["retry_result"] = True
            recovered_event["recovered_at"] = (
                datetime.now(timezone.utc).isoformat()
            )
            return

    setattr(subscribe, _TRANSPORT_OWNER, REVISION)
    subscribe._gs637_original = current
    owner.subscribe = subscribe
    return True


def _consume_transport_recovery(provider, trace: dict) -> None:
    subscription = getattr(provider, "_subscription", None)
    transport = getattr(subscription, "transport", None)
    event = getattr(transport, "_gs637_recovery_event", None)
    if not isinstance(event, dict) or event.get("consumed"):
        return

    event["consumed"] = True
    trace["same_transport_retry_attempts"] = int(
        trace.get("same_transport_retry_attempts") or 0
    ) + 1
    if event.get("retry_result"):
        trace["same_transport_retry_successes"] = int(
            trace.get("same_transport_retry_successes") or 0
        ) + 1
    trace["last_detected_at"] = event.get("detected_at")
    trace["last_failure"] = event.get("first_failure")
    trace["last_retry_result"] = bool(event.get("retry_result"))


def install_for_provider(provider) -> bool:
    """Install diagnostics outside the existing stream guard chain."""
    transport_changed = _install_transport_patch()
    if provider is None:
        return transport_changed

    current = getattr(provider, "ensure_stream", None)
    if not callable(current):
        return transport_changed
    function = getattr(current, "__func__", current)
    if (
        getattr(function, _OWNER, None) == REVISION
        or getattr(current, _OWNER, None) == REVISION
    ):
        return transport_changed

    @wraps(current)
    def guarded(symbols):
        stream = _stream(provider)
        trace = _trace(provider)
        _refresh_tick_truth(provider, trace)
        failures_before = len(
            list(stream.get("subscription_failures") or [])
        )
        result = current(_symbols(symbols))
        failures_after = list(stream.get("subscription_failures") or [])

        _consume_transport_recovery(provider, trace)
        if not result:
            newest = (
                failures_after[-1]
                if len(failures_after) > failures_before
                else None
            )
            if _invalid_session_failure(newest):
                trace["terminal_invalid_session_failures"] = int(
                    trace.get("terminal_invalid_session_failures") or 0
                ) + 1
                trace["same_transport_retry_attempts"] = int(
                    trace.get("same_transport_retry_attempts") or 0
                ) + 1
                trace["last_detected_at"] = (
                    datetime.now(timezone.utc).isoformat()
                )
                trace["last_failure"] = str(newest)
                trace["last_retry_result"] = False

        _refresh_tick_truth(provider, trace)
        trace["last_result"] = bool(result)
        return result

    setattr(guarded, _OWNER, REVISION)
    guarded._gs637_original = current
    try:
        provider.ensure_stream = guarded
    except (AttributeError, TypeError):
        return transport_changed
    return True


__all__ = [
    "AUTHORITY",
    "INVALID_SESSION_RETRY_DELAY_SECONDS",
    "REVISION",
    "install_for_provider",
]

"""GS347: bound native Webull radar calls so one hung SDK request cannot freeze Walter.

Live evidence on 2026-09-01 showed the Streamlit browser session repeatedly entering
CONNECTING while the local network and Webull Desktop remained healthy. Walter's
native-radar discovery path performs synchronous SDK screener calls on the
Streamlit execution thread. If one of those calls never returns, the entire app
can become unresponsive until a reboot.

GS347 wraps the complete native-radar discovery operation in a daemon worker with
a hard wall-clock timeout and a short circuit-breaker cooldown. On timeout Walter
fails closed, records explicit runtime-health diagnostics, and subsequent scans
fail fast during the cooldown rather than creating more blocked work.

This changes transport reliability only. It does not change discovery feeds,
symbol membership, scoring, qualification, VWAP, readiness, ranking, alerts,
execution, orders, or trading logic.
"""
from __future__ import annotations

from datetime import datetime, timezone
import queue
import threading
import time
from typing import Any, Callable

RADAR_TIMEOUT_SECONDS = 12.0
RADAR_COOLDOWN_SECONDS = 120.0

_lock = threading.Lock()
_cooldown_until = 0.0
_timeout_count = 0
_last_timeout_utc: str | None = None
_last_success_utc: str | None = None
_last_duration_seconds: float | None = None


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def reset_runtime_health() -> None:
    global _cooldown_until, _timeout_count, _last_timeout_utc, _last_success_utc
    global _last_duration_seconds
    with _lock:
        _cooldown_until = 0.0
        _timeout_count = 0
        _last_timeout_utc = None
        _last_success_utc = None
        _last_duration_seconds = None


def runtime_health(*, now: float | None = None) -> dict[str, Any]:
    now = time.monotonic() if now is None else now
    with _lock:
        remaining = max(0.0, _cooldown_until - now)
        return {
            "state": "DEGRADED" if remaining > 0 else "READY",
            "radar_timeout_seconds": RADAR_TIMEOUT_SECONDS,
            "cooldown_seconds_remaining": round(remaining, 3),
            "timeout_count": _timeout_count,
            "last_timeout_utc": _last_timeout_utc,
            "last_success_utc": _last_success_utc,
            "last_duration_seconds": _last_duration_seconds,
        }


def _publish(client: Any, health: dict[str, Any], *, error: str = "") -> None:
    diagnostics = getattr(client, "diagnostics", None)
    if not isinstance(diagnostics, dict):
        return
    section = diagnostics.setdefault("webull_native_health", {})
    section.update(health)
    section["error"] = error


def _bounded_daemon_call(call: Callable[[], Any], timeout_seconds: float) -> Any:
    """Run *call* outside Streamlit's script thread and stop waiting at timeout.

    The worker is daemonized intentionally: a permanently blocked vendor SDK call
    must not prevent process replacement during a Streamlit reboot/deploy.
    """
    result_queue: queue.Queue[tuple[str, Any]] = queue.Queue(maxsize=1)

    def worker() -> None:
        try:
            result_queue.put(("ok", call()), block=False)
        except BaseException as exc:  # return the original exception to caller
            try:
                result_queue.put(("error", exc), block=False)
            except queue.Full:
                pass

    thread = threading.Thread(target=worker, name="walter-webull-radar", daemon=True)
    thread.start()
    try:
        status, value = result_queue.get(timeout=max(0.001, float(timeout_seconds)))
    except queue.Empty as exc:
        raise TimeoutError(
            f"Webull native radar timed out after {float(timeout_seconds):.1f}s"
        ) from exc
    if status == "error":
        raise value
    return value


def guarded_fetch(fetch: Callable[[Any], dict], client: Any, *,
                  timeout_seconds: float = RADAR_TIMEOUT_SECONDS,
                  cooldown_seconds: float = RADAR_COOLDOWN_SECONDS,
                  now: Callable[[], float] = time.monotonic) -> dict:
    """Execute one native-radar fetch with timeout, health state, and cooldown."""
    global _cooldown_until, _timeout_count, _last_timeout_utc, _last_success_utc
    global _last_duration_seconds

    started = now()
    with _lock:
        remaining = _cooldown_until - started
    if remaining > 0:
        health = runtime_health(now=started)
        message = (
            "Webull native radar temporarily disabled after a prior timeout; "
            f"retry in {remaining:.0f}s"
        )
        _publish(client, health, error=message)
        raise RuntimeError(message)

    try:
        report = _bounded_daemon_call(lambda: fetch(client), timeout_seconds)
    except TimeoutError as exc:
        finished = now()
        with _lock:
            _timeout_count += 1
            _last_timeout_utc = _utc_now()
            _last_duration_seconds = max(0.0, finished - started)
            _cooldown_until = finished + max(0.0, float(cooldown_seconds))
        _publish(client, runtime_health(now=finished), error=str(exc))
        raise
    except Exception as exc:
        finished = now()
        with _lock:
            _last_duration_seconds = max(0.0, finished - started)
        health = runtime_health(now=finished)
        health["state"] = "DEGRADED"
        _publish(client, health, error=f"{type(exc).__name__}: {exc}")
        raise

    finished = now()
    with _lock:
        _cooldown_until = 0.0
        _last_success_utc = _utc_now()
        _last_duration_seconds = max(0.0, finished - started)
    _publish(client, runtime_health(now=finished), error="")
    if isinstance(report, dict):
        report = dict(report)
        report["runtime_health"] = runtime_health(now=finished)
    return report


def install() -> None:
    """Wrap both runtime bindings of native-radar discovery exactly once."""
    from . import webull_connection as connection
    from . import webull_native_radar as radar

    current = connection.fetch_native_radar
    if getattr(current, "_gs347_native_radar_timeout_health", False):
        return

    def fetch_with_health(client):
        return guarded_fetch(current, client)

    for name, value in getattr(current, "__dict__", {}).items():
        if name.startswith("_gs"):
            setattr(fetch_with_health, name, value)
    fetch_with_health._gs347_native_radar_timeout_health = True
    fetch_with_health._gs347_original = current

    connection.fetch_native_radar = fetch_with_health
    # Keep diagnostics/tests that call the canonical module binding on the same
    # reliability contract, without double-wrapping connection's captured call.
    radar.fetch_native_radar = fetch_with_health

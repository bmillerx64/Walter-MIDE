"""GS357: bound Webull history calls so one stalled SDK request cannot freeze Walter.

Reliability only. This does not change discovery membership, scoring, thresholds,
qualification, ranking, alerts, execution, or order behavior. A timed-out Webull
history request fails the current scan so Walter preserves the last completed
scan instead of blocking the Streamlit session indefinitely.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from datetime import datetime, timezone
import logging
import threading
import time
from typing import Any, Callable


LOGGER = logging.getLogger(__name__)
HISTORY_CALL_TIMEOUT_SECONDS = 10
HISTORY_CIRCUIT_SECONDS = 30
_HISTORY_EXECUTOR = ThreadPoolExecutor(max_workers=2, thread_name_prefix="walter-history-guard")
_HEALTH_LOCK = threading.Lock()
_HEALTH: dict[str, Any] = {
    "timeout_count": 0,
    "circuit_skip_count": 0,
    "last_timeout_at": None,
    "last_timeout_symbols": [],
    "last_timeout_reason": "",
    "circuit_open_until_monotonic": 0.0,
}


class WebullHistoryTimeout(TimeoutError):
    """Raised when Webull history exceeds Walter's bounded scan budget."""


def _symbols(values) -> list[str]:
    return list(dict.fromkeys(
        str(value or "").strip().upper() for value in values if str(value or "").strip()
    ))


def _open_circuit(*, symbols: list[str], reason: str) -> None:
    with _HEALTH_LOCK:
        _HEALTH["timeout_count"] = int(_HEALTH.get("timeout_count") or 0) + 1
        _HEALTH["last_timeout_at"] = datetime.now(timezone.utc).isoformat()
        _HEALTH["last_timeout_symbols"] = list(symbols)
        _HEALTH["last_timeout_reason"] = reason
        _HEALTH["circuit_open_until_monotonic"] = time.monotonic() + HISTORY_CIRCUIT_SECONDS


def _circuit_open() -> bool:
    with _HEALTH_LOCK:
        return time.monotonic() < float(_HEALTH.get("circuit_open_until_monotonic") or 0.0)


def runtime_health() -> dict[str, Any]:
    """Return non-sensitive history-timeout telemetry for operator diagnostics."""
    with _HEALTH_LOCK:
        snapshot = dict(_HEALTH)
    remaining = max(
        0.0,
        float(snapshot.get("circuit_open_until_monotonic") or 0.0) - time.monotonic(),
    )
    return {
        "state": "DEGRADED" if remaining > 0 else "READY",
        "timeout_count": int(snapshot.get("timeout_count") or 0),
        "circuit_skip_count": int(snapshot.get("circuit_skip_count") or 0),
        "last_timeout_at": snapshot.get("last_timeout_at"),
        "last_timeout_symbols": list(snapshot.get("last_timeout_symbols") or []),
        "last_timeout_reason": str(snapshot.get("last_timeout_reason") or ""),
        "circuit_seconds_remaining": round(remaining, 1),
    }


def _record_client_timeout(client, symbols: list[str], reason: str, *, circuit_skip: bool) -> None:
    diagnostics = getattr(client, "history_call_diagnostics", None)
    if isinstance(diagnostics, dict):
        key = "circuit_skips" if circuit_skip else "timeouts"
        diagnostics[key] = int(diagnostics.get(key) or 0) + 1
        diagnostics["last_timeout_reason"] = reason
        diagnostics["last_timeout_symbols"] = list(symbols)


def bounded_history_call(
    call: Callable[[], Any],
    *,
    client,
    symbols: list[str],
    timeout_seconds: float = HISTORY_CALL_TIMEOUT_SECONDS,
) -> Any:
    """Run one history request with a hard caller-side wait budget.

    The underlying SDK worker may finish later, but Streamlit is never required
    to wait beyond this budget. The short circuit prevents repeated scans from
    piling additional history calls onto already-busy workers.
    """
    if _circuit_open():
        reason = "Webull history circuit is cooling down after a prior timeout"
        with _HEALTH_LOCK:
            _HEALTH["circuit_skip_count"] = int(_HEALTH.get("circuit_skip_count") or 0) + 1
        _record_client_timeout(client, symbols, reason, circuit_skip=True)
        raise WebullHistoryTimeout(reason)

    future = _HISTORY_EXECUTOR.submit(call)
    try:
        return future.result(timeout=max(0.1, float(timeout_seconds)))
    except FutureTimeoutError as exc:
        future.cancel()
        reason = f"Webull history exceeded {timeout_seconds:g}s scan budget"
        _open_circuit(symbols=symbols, reason=reason)
        _record_client_timeout(client, symbols, reason, circuit_skip=False)
        LOGGER.error(
            "WEBULL history containment timeout symbols=%d budget_seconds=%s; "
            "failing scan and preserving last completed result",
            len(symbols), timeout_seconds,
        )
        raise WebullHistoryTimeout(reason) from exc


def install() -> None:
    """Wrap the final installed Webull history adapter with bounded waiting."""
    from . import webull_live

    current = webull_live.WebullOpenAPIClient.bars
    if getattr(current, "_gs357_history_timeout_containment", False):
        return

    def bounded_bars(self, symbols, *, start, timeframe="1Min", limit=10_000, **kwargs):
        wanted = _symbols(symbols)
        # Preserve fast local validation (notably unsupported 30-second bars)
        # without needlessly sending it through a worker.
        if str(timeframe).strip().lower() in {"30sec", "30s", "s30"}:
            return current(
                self, wanted, start=start, timeframe=timeframe, limit=limit, **kwargs
            )
        return bounded_history_call(
            lambda: current(
                self, wanted, start=start, timeframe=timeframe, limit=limit, **kwargs
            ),
            client=self,
            symbols=wanted,
        )

    bounded_bars._gs357_history_timeout_containment = True
    bounded_bars._gs357_original = current
    webull_live.WebullOpenAPIClient.bars = bounded_bars

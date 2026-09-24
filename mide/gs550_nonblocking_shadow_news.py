"""GS550: keep Alpaca shadow-news observation off Walter's blocking scan path.

GS544/GS547 are forensic-only. Live validation after GS549 proved that an external
shadow-news request can keep a Streamlit scan rerun occupied long enough to starve
AutoScan cadence, stale the rendered board, and prevent prepared download buttons
from being serviced. Trading evidence must never wait for observation-only news.

GS550 runs at most one shadow observer worker per retained LiveWebullProvider. The
worker may update diagnostics for the *next* completed scan, but the current scan
returns immediately. No shadow article is granted catalyst or trading authority.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import threading
from typing import Any, Callable, Iterable


AUTHORITY = "NONBLOCKING_SHADOW_NEWS_OBSERVATION_ONLY"
_JOB_ATTR = "_gs550_shadow_news_job"


def _runtime_diagnostics(client: Any) -> dict:
    diagnostics = getattr(client, "diagnostics", None)
    if not isinstance(diagnostics, dict):
        return {}
    runtime = diagnostics.setdefault("gs550_shadow_news_runtime", {})
    return runtime if isinstance(runtime, dict) else {}


def schedule_observation(
    source_client: Any,
    observer_client: Any,
    observe_shadow: Callable[..., dict],
    symbols: Iterable[str],
    primary_news_items: Iterable[dict],
    *,
    facade_used: bool = False,
) -> dict:
    """Start one daemon observer if needed and return without waiting for I/O."""
    existing = getattr(source_client, _JOB_ATTR, None)
    if isinstance(existing, dict):
        thread = existing.get("thread")
        if isinstance(thread, threading.Thread) and thread.is_alive():
            runtime = _runtime_diagnostics(source_client)
            runtime.update(
                {
                    "authority": AUTHORITY,
                    "status": "running",
                    "worker_reused": True,
                    "scan_blocked": False,
                    "trading_authority_changed": False,
                }
            )
            return dict(runtime)

    symbols_snapshot = tuple(
        str(symbol or "").strip().upper()
        for symbol in symbols or ()
        if str(symbol or "").strip()
    )
    news_snapshot = tuple(deepcopy(list(primary_news_items or ())))

    runtime = _runtime_diagnostics(source_client)
    runtime.clear()
    runtime.update(
        {
            "authority": AUTHORITY,
            "status": "running",
            "worker_reused": False,
            "started_at_utc": datetime.now(timezone.utc).isoformat(),
            "scan_blocked": False,
            "trading_authority_changed": False,
        }
    )

    state: dict[str, Any] = {}

    def worker() -> None:
        try:
            trace = observe_shadow(
                observer_client,
                symbols_snapshot,
                news_snapshot,
            )
            if not isinstance(trace, dict):
                trace = {
                    "authority": "NEWS_COVERAGE_OBSERVATION_ONLY",
                    "request_made": False,
                    "reason": "shadow observer returned no diagnostic mapping",
                    "trading_authority_changed": False,
                }
            else:
                trace = deepcopy(trace)
            trace["warm_deploy_news_facade_used"] = bool(facade_used)
            trace["warm_deploy_news_facade_authority"] = (
                "WARM_DEPLOY_SHADOW_NEWS_FACADE"
            )
            trace["nonblocking_scan_authority"] = AUTHORITY
            trace["scan_blocked"] = False
            diagnostics = getattr(source_client, "diagnostics", None)
            if isinstance(diagnostics, dict):
                diagnostics["gs544_alpaca_news_shadow"] = trace
            runtime.update(
                {
                    "status": "completed",
                    "finished_at_utc": datetime.now(timezone.utc).isoformat(),
                    "scan_blocked": False,
                }
            )
        except Exception as exc:
            diagnostics = getattr(source_client, "diagnostics", None)
            if isinstance(diagnostics, dict):
                diagnostics["gs544_alpaca_news_shadow"] = {
                    "authority": "NEWS_COVERAGE_OBSERVATION_ONLY",
                    "request_made": False,
                    "reason": (
                        f"nonblocking shadow observer unavailable: "
                        f"{type(exc).__name__}: {exc}"
                    )[:500],
                    "warm_deploy_news_facade_used": bool(facade_used),
                    "warm_deploy_news_facade_authority": (
                        "WARM_DEPLOY_SHADOW_NEWS_FACADE"
                    ),
                    "nonblocking_scan_authority": AUTHORITY,
                    "scan_blocked": False,
                    "trading_authority_changed": False,
                }
            runtime.update(
                {
                    "status": "failed",
                    "finished_at_utc": datetime.now(timezone.utc).isoformat(),
                    "error_type": type(exc).__name__,
                    "error_message": str(exc)[:500],
                    "scan_blocked": False,
                }
            )

    thread = threading.Thread(
        target=worker,
        name="walter-gs550-shadow-news",
        daemon=True,
    )
    state["thread"] = thread
    setattr(source_client, _JOB_ATTR, state)
    thread.start()
    return dict(runtime)


__all__ = ["AUTHORITY", "schedule_observation"]

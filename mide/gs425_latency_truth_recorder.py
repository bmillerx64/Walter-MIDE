"""GS425: warm-deploy-safe compatibility facade for live-scan latency truth.

Phase 30 moves GS425's latency evidence algorithms and recorder/history wrappers into
Walter Next's authoritative Replay / Validation component. GS425 retains its historical
thread-local trace object because GS427/GS472 and regression tests intentionally use
that state/seam to identify the exact Stage-6 provider that completed the scan.

The authority is resolved lazily. If a warm Streamlit process retains an older
Replay / Validation generation that does not yet expose GS425, install() safely leaves
the already-active legacy wrapper in place instead of crashing startup. A clean
runtime binds the consolidated implementation normally.

This remains observational only: no provider request is added and no market-data
value, indicator, score, threshold, qualification, alert, execution, or order behavior
is changed.
"""
from __future__ import annotations

from threading import local
from typing import Any, Iterable


AUTHORITY = "OBSERVATIONAL_ONLY"
_STAGE6_PREFIX = "stage6_"
_TRACE = local()


def _replay():
    from mide.authorities import replay_validation

    return replay_validation


def _normalize_symbols(symbols: Iterable[str] | None) -> list[str]:
    current = getattr(_replay(), "normalize_latency_symbols", None)
    if callable(current):
        return current(symbols)
    return list(
        dict.fromkeys(
            str(symbol or "").strip().upper()
            for symbol in (symbols or [])
            if str(symbol or "").strip()
        )
    )


def _history_diagnostics(provider) -> dict[str, int]:
    current = getattr(_replay(), "latency_history_diagnostics", None)
    if not callable(current):
        return {}
    return current(provider)


def _provider_from_trace():
    current = getattr(_replay(), "latency_provider_from_trace", None)
    if not callable(current):
        reference = getattr(_TRACE, "provider", None)
        if reference is None:
            return None
        try:
            return reference()
        except TypeError:
            return None
    return current()


def _trace_events() -> list[dict[str, Any]]:
    current = getattr(_replay(), "latency_trace_events", None)
    if callable(current):
        return current()
    events = getattr(_TRACE, "events", None)
    if not isinstance(events, list):
        events = []
        _TRACE.events = events
    return events


def _reset_trace(provider) -> None:
    current = getattr(_replay(), "reset_latency_trace", None)
    if not callable(current):
        import weakref

        _TRACE.events = []
        _TRACE.provider = weakref.ref(provider)
        return
    current(provider)


def _append_history_event(provider, **kwargs) -> None:
    current = getattr(_replay(), "append_latency_history_event", None)
    if not callable(current):
        return
    current(provider, **kwargs)


def build_latency_truth(
    provider,
    events: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    current = getattr(_replay(), "build_latency_truth", None)
    if not callable(current):
        raise RuntimeError(
            "Current Replay / Validation generation does not yet expose GS425"
        )
    return current(provider, events)


def install() -> None:
    current = getattr(_replay(), "install_latency_truth_recorder", None)
    if not callable(current):
        # Warm-deploy safety: pre-Phase-30 GS425 may already own the live wrappers.
        return
    current()


def __getattr__(name: str):
    try:
        return getattr(_replay(), name)
    except AttributeError:
        raise AttributeError(name) from None


__all__ = ["AUTHORITY", "build_latency_truth", "install"]

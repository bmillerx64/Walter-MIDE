"""GS425: persist exact live-scan latency truth so the next optimization is evidence-led.

GS424 reduced repeated history payloads but Sep. 10 live validation still showed
roughly 83-90 seconds from scan attempt to Flight Recorder persistence.  The app
already computes a full pipeline timing summary and the Webull adapter already knows
its history-call counters, but neither survived into the downloaded Flight Recorder.
That left operator-observed latency measurable but its internal owner ambiguous.

GS425 is observational only.  It times the existing Stage-6 Webull history boundary,
records whether GS424 was actually warm, captures the already-computed architecture
timing summary, and writes that compact evidence into the same completed Flight
Recorder scan.  A process-local provider instance token also reveals whether a warm
Streamlit rerun reused the same provider or a different session/provider performed the
scan.  No provider request, market-data value, indicator, score, threshold,
qualification, alert, execution, or order behavior is changed.
"""
from __future__ import annotations

from copy import deepcopy
from functools import wraps
from threading import local
from time import monotonic
from typing import Any, Iterable
import weakref

from . import flight_recorder
from .webull_live import LiveWebullProvider


AUTHORITY = "OBSERVATIONAL_ONLY"
_STAGE6_PREFIX = "stage6_"
_TRACE = local()
_INSTALL_GENERATION = object()


def _normalize_symbols(symbols: Iterable[str] | None) -> list[str]:
    return list(
        dict.fromkeys(
            str(symbol or "").strip().upper()
            for symbol in (symbols or [])
            if str(symbol or "").strip()
        )
    )


def _history_diagnostics(provider: LiveWebullProvider | None) -> dict[str, int]:
    client = getattr(provider, "_snapshot_client", None) if provider is not None else None
    raw = getattr(client, "history_call_diagnostics", None)
    if not isinstance(raw, dict):
        return {}
    result = {}
    for key in ("batch_calls", "single_fallback_calls"):
        try:
            result[key] = int(raw.get(key, 0) or 0)
        except (TypeError, ValueError):
            result[key] = 0
    return result


def _provider_from_trace() -> LiveWebullProvider | None:
    reference = getattr(_TRACE, "provider", None)
    if reference is None:
        return None
    try:
        return reference()
    except TypeError:
        return None


def _trace_events() -> list[dict[str, Any]]:
    events = getattr(_TRACE, "events", None)
    if not isinstance(events, list):
        events = []
        _TRACE.events = events
    return events


def _reset_trace(provider: LiveWebullProvider) -> None:
    _TRACE.events = []
    _TRACE.provider = weakref.ref(provider)


def _append_history_event(
    provider: LiveWebullProvider,
    *,
    reason: str,
    timeframe: str,
    symbols: list[str],
    kwargs: dict[str, Any],
    elapsed_ms: float,
    before: dict[str, int],
    after: dict[str, int],
    success: bool,
    result: Any = None,
    exception: Exception | None = None,
) -> None:
    if not reason.startswith(_STAGE6_PREFIX):
        return
    diagnostics = getattr(provider, "diagnostics", None)
    cache = (
        deepcopy(diagnostics.get("gs424_warm_scan_history_cache") or {})
        if isinstance(diagnostics, dict)
        else {}
    )
    returned_symbols = len(result) if isinstance(result, dict) else 0
    returned_rows = (
        sum(len(rows or []) for rows in result.values())
        if isinstance(result, dict)
        else 0
    )
    event = {
        "reason": reason,
        "timeframe": timeframe,
        "symbol_count": len(symbols),
        "symbols": symbols,
        "requested_start": str(kwargs.get("start")) if kwargs.get("start") is not None else None,
        "requested_end": str(kwargs.get("end")) if kwargs.get("end") is not None else None,
        "limit": kwargs.get("limit"),
        "force_batch": bool(kwargs.get("force_batch")),
        "elapsed_ms": round(float(elapsed_ms), 3),
        "success": bool(success),
        "returned_symbols": returned_symbols,
        "returned_rows": returned_rows,
        "batch_calls_delta": max(0, after.get("batch_calls", 0) - before.get("batch_calls", 0)),
        "single_fallback_calls_delta": max(
            0,
            after.get("single_fallback_calls", 0)
            - before.get("single_fallback_calls", 0),
        ),
        "exception_class": type(exception).__name__ if exception is not None else None,
        "gs424": cache or None,
    }
    _trace_events().append(event)


def build_latency_truth(
    provider: LiveWebullProvider | None,
    events: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build a compact diagnostic package from evidence already produced this scan."""
    captured = deepcopy(events if events is not None else _trace_events())
    diagnostics = getattr(provider, "diagnostics", None)
    diagnostics = diagnostics if isinstance(diagnostics, dict) else {}
    pipeline = deepcopy(diagnostics.get("pipeline_timing_summary") or [])
    cache = deepcopy(diagnostics.get("gs424_warm_scan_history_cache") or {})
    state = getattr(provider, "_walter_gs424_history_cache", None)
    cached_rows = state.get("rows", {}) if isinstance(state, dict) else {}

    history_elapsed = sum(
        float(event.get("elapsed_ms") or 0.0)
        for event in captured
        if event.get("reason", "").startswith(_STAGE6_PREFIX)
    )
    slowest = max(
        captured,
        key=lambda event: float(event.get("elapsed_ms") or 0.0),
        default=None,
    )
    return {
        "authority": AUTHORITY,
        "purpose": "locate live scan latency without changing scan behavior",
        "provider_instance_token": (
            f"{id(provider):x}" if provider is not None else None
        ),
        "provider_reused_observable_on_next_scan": True,
        "pipeline_timing_summary": pipeline,
        "stage6_history_calls": captured,
        "stage6_history_elapsed_ms": round(history_elapsed, 3),
        "slowest_stage6_history_call": deepcopy(slowest),
        "history_call_diagnostics": _history_diagnostics(provider),
        "gs424_last_cache_observation": cache or None,
        "gs424_cached_symbol_count": len(cached_rows) if isinstance(cached_rows, dict) else 0,
        "market_data_values_changed": False,
        "trading_logic_changed": False,
    }


def install() -> None:
    """Install after GS424 so timings include the exact effective history boundary."""
    current_bars = LiveWebullProvider.bars
    if getattr(current_bars, "_gs425_install_generation", None) is not _INSTALL_GENERATION:
        @wraps(current_bars)
        def bars_with_latency_truth(self, symbols, **kwargs):
            wanted = _normalize_symbols(symbols)
            reason = str(kwargs.get("history_reason") or "")
            timeframe = str(kwargs.get("timeframe") or "1Min")
            if reason == "stage6_current_session":
                _reset_trace(self)
            elif reason.startswith(_STAGE6_PREFIX):
                _TRACE.provider = weakref.ref(self)

            before = _history_diagnostics(self)
            started = monotonic()
            result = None
            try:
                result = current_bars(self, wanted, **kwargs)
                return result
            except Exception as exc:
                after = _history_diagnostics(self)
                _append_history_event(
                    self,
                    reason=reason,
                    timeframe=timeframe,
                    symbols=wanted,
                    kwargs=kwargs,
                    elapsed_ms=(monotonic() - started) * 1000.0,
                    before=before,
                    after=after,
                    success=False,
                    result=None,
                    exception=exc,
                )
                raise
            finally:
                if result is not None:
                    after = _history_diagnostics(self)
                    _append_history_event(
                        self,
                        reason=reason,
                        timeframe=timeframe,
                        symbols=wanted,
                        kwargs=kwargs,
                        elapsed_ms=(monotonic() - started) * 1000.0,
                        before=before,
                        after=after,
                        success=True,
                        result=result,
                    )

        bars_with_latency_truth._gs425_latency_truth = True
        bars_with_latency_truth._gs425_install_generation = _INSTALL_GENERATION
        bars_with_latency_truth._gs425_original = current_bars
        LiveWebullProvider.bars = bars_with_latency_truth

    current_persist = flight_recorder.persist_replayable_scan
    if getattr(current_persist, "_gs425_install_generation", None) is _INSTALL_GENERATION:
        return

    @wraps(current_persist)
    def persist_with_latency_truth(recorder, scan, records, *, data_mode=None):
        provider = _provider_from_trace()
        augmented = dict(scan)
        augmented["latency_truth"] = build_latency_truth(provider)
        try:
            return current_persist(
                recorder, augmented, records, data_mode=data_mode
            )
        finally:
            _TRACE.events = []
            _TRACE.provider = None

    persist_with_latency_truth._gs425_latency_truth = True
    persist_with_latency_truth._gs425_install_generation = _INSTALL_GENERATION
    persist_with_latency_truth._gs425_original = current_persist
    flight_recorder.persist_replayable_scan = persist_with_latency_truth

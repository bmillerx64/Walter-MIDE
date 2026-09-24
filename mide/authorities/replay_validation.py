"""Authoritative Walter Next Replay / Validation boundary.

Stable recorder/outcome classes remain direct imports. Replaceable validation
functions resolve dynamically so warm Streamlit reruns cannot retain stale wrappers.
"""

from __future__ import annotations

from copy import deepcopy
from functools import wraps
import json
import re
import weakref
from pathlib import Path
from threading import local
from time import monotonic
from typing import Any, Iterable, Iterator

from mide.flight_recorder import FlightRecorder
from mide.mission_outcomes import MissionOutcomeStore


def _validation_number(
    record: dict,
    *keys: str,
    default: float | None = None,
) -> float | None:
    for key in keys:
        value = record.get(key)
        if value is None or value == "":
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return default


def build_validation_sequence_with_ignition(
    original,
    scan: dict,
    records,
    provider,
) -> dict:
    """Enrich GS390 replay output with authoritative primary-ignition truth."""
    from mide import gs390_st_vwap_validation_sequence as sequence
    from mide.authorities import market_evidence

    payload = original(scan, records, provider)
    payload = dict(payload)
    rows = [dict(item) for item in list(payload.get("symbols") or [])]
    by_symbol = {
        str(item.get("symbol") or "").upper(): item
        for item in rows
        if str(item.get("symbol") or "").strip()
    }

    for source in records or []:
        record = dict(source)
        symbol = str(record.get("symbol") or "").strip().upper()
        if not symbol:
            continue
        ignition = market_evidence.ignition_evidence(record)
        if not ignition.get("recent") and symbol not in by_symbol:
            continue

        row = by_symbol.get(symbol)
        if row is None:
            one = sequence._event(record, "1m")
            three = sequence._event(record, "3m")
            row = {
                "symbol": symbol,
                "scan_price": _validation_number(record, "price"),
                "participation_score": _validation_number(
                    record,
                    "participation_score",
                ),
                "participation_surge_score": _validation_number(
                    record,
                    "participation_surge_score",
                ),
                "volume_pace_ratio": _validation_number(
                    record,
                    "volume_pace_ratio",
                ),
                "participation_gate": dict(record.get("participation_gate") or {}),
                "thirty_second": sequence._thirty_second_context(
                    provider,
                    symbol,
                    sequence._timestamp_ms(one.get("bullish_flip_timestamp")),
                ),
                "one_minute": {
                    "current_state": sequence._timeframe_state(record, "1m"),
                    "literal_st_line_vwap_cross": one,
                },
                "three_minute": {
                    "current_state": sequence._timeframe_state(record, "3m"),
                    "literal_st_line_vwap_cross": three,
                },
                "price_response_since_1m_ignition_pct": None,
            }
            rows.append(row)
            by_symbol[symbol] = row

        row["operator_ignition"] = ignition
        if ignition.get("recent"):
            row["sequence"] = (
                "1m price/VWAP + bullish SuperTrend ignition observed; "
                + (
                    "3m confirmation present"
                    if ignition.get("three_minute_confirmation")
                    else "3m confirmation pending"
                )
            )
        row["literal_st_line_vwap_cross_role"] = "SECONDARY_MATURATION_EVIDENCE"

    payload["symbols"] = rows
    payload["symbol_count"] = len(rows)
    payload["primary_ignition_definition"] = (
        "fresh VWAP reclaim/hold + bullish 1m SuperTrend, or fresh bullish 1m "
        "SuperTrend flip while price is above VWAP and inside the +2% chase guard"
    )
    payload["three_minute_role"] = "CONFIRMATION_NOT_PERMISSION"
    return payload


def install_ignition_validation_sequence() -> None:
    """Bind GS393 replay enrichment at its historical recorder install position."""
    from mide import gs390_st_vwap_validation_sequence as sequence

    current = sequence.build_validation_sequence
    if getattr(current, "_gs393_ignition_truth", False):
        return

    def build_with_ignition(scan: dict, records, provider) -> dict:
        return build_validation_sequence_with_ignition(
            current,
            scan,
            records,
            provider,
        )

    build_with_ignition._gs393_ignition_truth = True
    build_with_ignition._gs393_original = current
    sequence.build_validation_sequence = build_with_ignition


def prefilter_decision(*args, **kwargs):
    from mide import flight_recorder
    return flight_recorder.prefilter_decision(*args, **kwargs)


def scan_integrity_report(*args, **kwargs):
    from mide import data_integrity
    return data_integrity.scan_integrity_report(*args, **kwargs)


# ---------------------------------------------------------------------------
# GS480 catalyst-story Flight Recorder truth
# ---------------------------------------------------------------------------

_CATALYST_STORY_RECORDER_OWNER = "_walter_gs480_story_recorder_owner"


def catalyst_story_trace_snapshots() -> tuple[list[dict], dict[str, dict]]:
    """Read GS480 compatibility snapshots without replacing authoritative containers."""
    from mide import gs480_catalyst_story_intelligence as gs480

    marketwide = getattr(gs480, "_LATEST_MARKETWIDE_TRACE", []) or []
    targeted = getattr(gs480, "_LATEST_TARGETED_TRACE", {}) or {}
    return marketwide, targeted


def catalyst_story_recorder_wrapper(current):
    """Persist story/news evidence through Replay / Validation ownership."""
    if not callable(current) or getattr(current, _CATALYST_STORY_RECORDER_OWNER, False):
        return current

    @wraps(current)
    def persist(self, scan, records):
        marketwide, targeted_trace = catalyst_story_trace_snapshots()
        record_by_symbol = {
            str(item.get("symbol") or "").strip().upper(): item
            for item in records or []
            if item.get("symbol")
        }
        for path in scan.get("symbols", []) if isinstance(scan, dict) else []:
            symbol = str(path.get("symbol") or "").strip().upper()
            evidence = path.setdefault("evidence", {})
            record = record_by_symbol.get(symbol) or {}
            targeted = targeted_trace.get(symbol) or {}
            headline = record.get("headline") or targeted.get("headline")
            if headline:
                evidence.update({
                    "news_headline": str(headline)[:500],
                    "news_created_at": record.get("news_created_at") or targeted.get("created_at"),
                    "news_age_seconds_at_scan": record.get(
                        "news_age_seconds_at_scan", targeted.get("age_seconds_at_scan")
                    ),
                    "news_source": record.get("news_source") or targeted.get("source"),
                    "news_provider": record.get("news_provider") or targeted.get("provider"),
                    "news_catalyst_score": record.get(
                        "catalyst_score", targeted.get("catalyst_score")
                    ),
                    "news_explicit_symbols": list(
                        record.get("news_explicit_symbols")
                        or targeted.get("explicit_symbols")
                        or []
                    ),
                    "catalyst_story": deepcopy(
                        record.get("catalyst_story")
                        or targeted.get("story_context")
                        or {}
                    ),
                    "news_marketwide_handoff": bool(
                        record.get(
                            "news_marketwide_handoff",
                            targeted.get("marketwide_handoff"),
                        )
                    ),
                })
        if isinstance(scan, dict):
            scan["news_trace"] = {
                "authority": "NEWS_AWARENESS_AND_OBSERVABILITY_ONLY",
                "marketwide_selected": deepcopy(list(marketwide)),
                "targeted": deepcopy(list(targeted_trace.values())),
                "additional_provider_requests": 0,
            }
        return current(self, scan, records)

    setattr(persist, _CATALYST_STORY_RECORDER_OWNER, True)
    persist._gs480_original = current
    return persist


def install_catalyst_story_trace() -> None:
    """Bind GS480 Flight Recorder story truth at its historical install position."""
    from mide import flight_recorder

    flight_recorder.persist_replayable_scan = catalyst_story_recorder_wrapper(
        flight_recorder.persist_replayable_scan
    )
    try:
        from mide import gs427_flight_recorder_latency_hard_bind as gs427
        globals_dict = gs427._active_recorder_globals()
    except Exception:
        globals_dict = {}
    if isinstance(globals_dict, dict):
        active = globals_dict.get("persist_replayable_scan")
        wrapped = catalyst_story_recorder_wrapper(active)
        if callable(wrapped):
            globals_dict["persist_replayable_scan"] = wrapped


# ---------------------------------------------------------------------------
# GS502 Benzinga breaking-news Flight Recorder trace
# ---------------------------------------------------------------------------

_BENZINGA_RECORDER_OWNER = "_walter_gs502_benzinga_breaking_recorder_owner"


def benzinga_breaking_news_trace_snapshot() -> dict:
    """Read the current GS502 compatibility trace without freezing its container."""
    from mide import gs502_benzinga_breaking_news as gs502

    return deepcopy(dict(getattr(gs502, "_LATEST_TRACE", {}) or {}))


def benzinga_breaking_news_recorder_wrapper(current):
    """Persist the bounded GS502 transport/selection trace."""
    if not callable(current) or getattr(current, _BENZINGA_RECORDER_OWNER, False):
        return current

    @wraps(current)
    def persist_with_breaking_news(recorder, scan: dict, records, *args, **kwargs):
        augmented = dict(scan)
        augmented["benzinga_breaking_news_trace"] = (
            benzinga_breaking_news_trace_snapshot()
        )
        return current(recorder, augmented, records, *args, **kwargs)

    setattr(persist_with_breaking_news, _BENZINGA_RECORDER_OWNER, True)
    persist_with_breaking_news._gs502_benzinga_breaking_news = True
    persist_with_breaking_news._gs502_original = current
    return persist_with_breaking_news


def install_benzinga_breaking_news_trace() -> None:
    """Bind GS502 recorder truth through Replay / Validation ownership."""
    from mide import flight_recorder
    from mide import gs427_flight_recorder_latency_hard_bind as gs427

    globals_dict = gs427._active_recorder_globals()
    current = globals_dict.get("persist_replayable_scan")
    wrapped = benzinga_breaking_news_recorder_wrapper(current)
    if callable(wrapped):
        globals_dict["persist_replayable_scan"] = wrapped
        if globals_dict is flight_recorder.__dict__:
            flight_recorder.persist_replayable_scan = wrapped


# ---------------------------------------------------------------------------
# GS425 live-scan latency truth recorder
# ---------------------------------------------------------------------------

LATENCY_TRUTH_AUTHORITY = "OBSERVATIONAL_ONLY"
_LATENCY_STAGE6_PREFIX = "stage6_"
_LATENCY_INSTALL_GENERATION = object()


def _latency_state():
    """Return the historical GS425 compatibility state container."""
    from mide import gs425_latency_truth_recorder as gs425

    return gs425


def normalize_latency_symbols(symbols: Iterable[str] | None) -> list[str]:
    return list(
        dict.fromkeys(
            str(symbol or "").strip().upper()
            for symbol in (symbols or [])
            if str(symbol or "").strip()
        )
    )


def latency_history_diagnostics(provider) -> dict[str, int]:
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


def latency_provider_from_trace():
    state = _latency_state()
    reference = getattr(state._TRACE, "provider", None)
    if reference is None:
        return None
    try:
        return reference()
    except TypeError:
        return None


def latency_trace_events() -> list[dict[str, Any]]:
    state = _latency_state()
    events = getattr(state._TRACE, "events", None)
    if not isinstance(events, list):
        events = []
        state._TRACE.events = events
    return events


def reset_latency_trace(provider) -> None:
    state = _latency_state()
    state._TRACE.events = []
    state._TRACE.provider = weakref.ref(provider)


def append_latency_history_event(
    provider,
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
    if not reason.startswith(_LATENCY_STAGE6_PREFIX):
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
        "requested_start": (
            str(kwargs.get("start"))
            if kwargs.get("start") is not None
            else None
        ),
        "requested_end": (
            str(kwargs.get("end"))
            if kwargs.get("end") is not None
            else None
        ),
        "limit": kwargs.get("limit"),
        "force_batch": bool(kwargs.get("force_batch")),
        "elapsed_ms": round(float(elapsed_ms), 3),
        "success": bool(success),
        "returned_symbols": returned_symbols,
        "returned_rows": returned_rows,
        "batch_calls_delta": max(
            0,
            after.get("batch_calls", 0) - before.get("batch_calls", 0),
        ),
        "single_fallback_calls_delta": max(
            0,
            after.get("single_fallback_calls", 0)
            - before.get("single_fallback_calls", 0),
        ),
        "exception_class": (
            type(exception).__name__ if exception is not None else None
        ),
        "gs424": cache or None,
    }
    latency_trace_events().append(event)


def build_latency_truth(
    provider,
    events: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build compact scan-latency evidence from already-produced runtime state."""
    captured = deepcopy(
        events if events is not None else latency_trace_events()
    )
    diagnostics = getattr(provider, "diagnostics", None)
    diagnostics = diagnostics if isinstance(diagnostics, dict) else {}
    pipeline = deepcopy(diagnostics.get("pipeline_timing_summary") or [])
    cache = deepcopy(diagnostics.get("gs424_warm_scan_history_cache") or {})
    state = getattr(provider, "_walter_gs424_history_cache", None)
    cached_rows = state.get("rows", {}) if isinstance(state, dict) else {}

    history_elapsed = sum(
        float(event.get("elapsed_ms") or 0.0)
        for event in captured
        if str(event.get("reason") or "").startswith(_LATENCY_STAGE6_PREFIX)
    )
    slowest = max(
        captured,
        key=lambda event: float(event.get("elapsed_ms") or 0.0),
        default=None,
    )
    return {
        "authority": LATENCY_TRUTH_AUTHORITY,
        "purpose": "locate live scan latency without changing scan behavior",
        "provider_instance_token": (
            f"{id(provider):x}" if provider is not None else None
        ),
        "provider_reused_observable_on_next_scan": True,
        "pipeline_timing_summary": pipeline,
        "stage6_history_calls": captured,
        "stage6_history_elapsed_ms": round(history_elapsed, 3),
        "slowest_stage6_history_call": deepcopy(slowest),
        "history_call_diagnostics": latency_history_diagnostics(provider),
        "gs424_last_cache_observation": cache or None,
        "gs424_cached_symbol_count": (
            len(cached_rows) if isinstance(cached_rows, dict) else 0
        ),
        "market_data_values_changed": False,
        "trading_logic_changed": False,
    }


def install_latency_truth_recorder() -> None:
    """Install GS425 timing at the effective Stage-6 and recorder boundaries."""
    from mide import flight_recorder
    from mide import gs425_latency_truth_recorder as gs425
    from mide.webull_live import LiveWebullProvider

    current_bars = LiveWebullProvider.bars
    if (
        getattr(current_bars, "_gs425_install_generation", None)
        is not _LATENCY_INSTALL_GENERATION
    ):
        @wraps(current_bars)
        def bars_with_latency_truth(self, symbols, **kwargs):
            wanted = gs425._normalize_symbols(symbols)
            reason = str(kwargs.get("history_reason") or "")
            timeframe = str(kwargs.get("timeframe") or "1Min")
            if reason == "stage6_current_session":
                gs425._reset_trace(self)
            elif reason.startswith(_LATENCY_STAGE6_PREFIX):
                gs425._TRACE.provider = weakref.ref(self)

            before = gs425._history_diagnostics(self)
            started = monotonic()
            result = None
            try:
                result = current_bars(self, wanted, **kwargs)
                return result
            except Exception as exc:
                after = gs425._history_diagnostics(self)
                gs425._append_history_event(
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
                    after = gs425._history_diagnostics(self)
                    gs425._append_history_event(
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
        bars_with_latency_truth._gs425_install_generation = (
            _LATENCY_INSTALL_GENERATION
        )
        bars_with_latency_truth._gs425_original = current_bars
        LiveWebullProvider.bars = bars_with_latency_truth

    current_persist = flight_recorder.persist_replayable_scan
    if (
        getattr(current_persist, "_gs425_install_generation", None)
        is _LATENCY_INSTALL_GENERATION
    ):
        return

    @wraps(current_persist)
    def persist_with_latency_truth(
        recorder,
        scan,
        records,
        *,
        data_mode=None,
    ):
        provider = gs425._provider_from_trace()
        augmented = dict(scan)
        augmented["latency_truth"] = gs425.build_latency_truth(provider)
        try:
            return current_persist(
                recorder,
                augmented,
                records,
                data_mode=data_mode,
            )
        finally:
            gs425._TRACE.events = []
            gs425._TRACE.provider = None

    persist_with_latency_truth._gs425_latency_truth = True
    persist_with_latency_truth._gs425_install_generation = (
        _LATENCY_INSTALL_GENERATION
    )
    persist_with_latency_truth._gs425_original = current_persist
    flight_recorder.persist_replayable_scan = persist_with_latency_truth


# ---------------------------------------------------------------------------
# GS481/GS484/GS485/GS486 live transport observability stack
# ---------------------------------------------------------------------------

LIVE_OBSERVABILITY_AUTHORITY = "OBSERVATIONAL_ONLY"

_LIVE_EVIDENCE_OWNER = "_walter_gs481_live_evidence_hard_bind_owner"
_FMP_TRANSPORT_OWNER = "_walter_gs484_fmp_transport_truth_owner"
_RETAINED_TRANSPORT_OWNER = "_walter_gs485_retained_news_transport_hard_bind_owner"
_TOP_LEVEL_TRANSPORT_OWNER = "_walter_gs486_top_level_transport_truth_owner"

LIVE_EVIDENCE_MAX_FAILURES = 3
LIVE_EVIDENCE_MAX_TEXT = 300
FMP_TRANSPORT_MAX_SYMBOLS = 80
FMP_TRANSPORT_MAX_FAILURES = 5


def sanitize_live_failure(value: Any) -> str:
    text = " ".join(str(value or "").split())
    if re.search(
        r"(?i)authorization|bearer|credential|password|secret|token|api[-_ ]?key|headers?",
        text,
    ):
        return "[redacted: potentially sensitive stream failure]"
    return text[:LIVE_EVIDENCE_MAX_TEXT]


def live_json_safe(value: Any):
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, dict):
        return {str(key): live_json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [live_json_safe(item) for item in value]
    if hasattr(value, "isoformat"):
        try:
            return value.isoformat()
        except Exception:
            pass
    return str(value)[:LIVE_EVIDENCE_MAX_TEXT]


def live_news_truth() -> dict:
    """Return bounded story/news recorder truth from GS480 compatibility state."""
    from mide import gs480_catalyst_story_intelligence as gs480

    marketwide = deepcopy(
        list(getattr(gs480, "_LATEST_MARKETWIDE_TRACE", []) or [])
    )
    targeted = deepcopy(
        dict(getattr(gs480, "_LATEST_TARGETED_TRACE", {}) or {})
    )
    selected = deepcopy(
        list(getattr(gs480, "_LAST_SELECTED", []) or [])
    )
    return {
        "authority": LIVE_OBSERVABILITY_AUTHORITY,
        "gs480_story_pipeline_present": True,
        "marketwide": live_json_safe(marketwide[-50:]),
        "targeted": live_json_safe(targeted),
        "selected": live_json_safe(selected[-50:]),
        "marketwide_count": len(marketwide),
        "targeted_count": len(targeted),
        "selected_count": len(selected),
        "extra_provider_calls": 0,
        "trading_authority_changed": False,
    }


def stream_failure_truth(provider) -> dict:
    diagnostics = getattr(provider, "diagnostics", None)
    stream = (
        diagnostics.get("webull_stream")
        if isinstance(diagnostics, dict)
        else None
    )
    stream = stream if isinstance(stream, dict) else {}
    failures = list(stream.get("subscription_failures") or [])
    return {
        "authority": LIVE_OBSERVABILITY_AUTHORITY,
        "connection_status": str(
            stream.get("stream_connection_status") or "unknown"
        ),
        "subscription_present": (
            getattr(provider, "_subscription", None) is not None
            if provider is not None
            else False
        ),
        "subscribed_symbol_count": (
            len(set(getattr(provider, "_subscribed", set()) or set()))
            if provider is not None
            else 0
        ),
        "disconnect_count": int(stream.get("disconnect_count", 0) or 0),
        "stream_replaced_count": int(
            stream.get("stream_replaced_count", 0) or 0
        ),
        "stream_cleanup_failures": int(
            stream.get("stream_cleanup_failures", 0) or 0
        ),
        "subscription_failure_count": len(failures),
        "subscription_failures_tail": [
            sanitize_live_failure(item)
            for item in failures[-LIVE_EVIDENCE_MAX_FAILURES:]
        ],
        "stream_bypass_reason": (
            sanitize_live_failure(stream.get("stream_bypass_reason"))
            if stream.get("stream_bypass_reason")
            else None
        ),
        "network_repair_attempted_here": False,
        "trading_authority_changed": False,
    }


def attach_stream_failure(scan: dict, provider) -> None:
    failure = stream_failure_truth(provider)
    health = dict(scan.get("stream_30s_health") or {})
    health["failure_diagnostics"] = failure
    scan["stream_30s_health"] = health

    identity = dict(scan.get("recorder_runtime_identity") or {})
    nested = dict(identity.get("stream_30s_health") or {})
    nested["failure_diagnostics"] = failure
    identity["stream_30s_health"] = nested
    scan["recorder_runtime_identity"] = identity


def install_live_evidence_hard_bind() -> None:
    """Bind GS481 observational truth to the retained active recorder graph."""
    from mide import flight_recorder
    from mide import gs427_flight_recorder_latency_hard_bind as gs427

    globals_dict = gs427._active_recorder_globals()
    current = globals_dict.get("persist_replayable_scan")
    if not callable(current):
        raise RuntimeError("Flight Recorder persistence callable is unavailable")
    if getattr(current, _LIVE_EVIDENCE_OWNER, False):
        return

    @wraps(current)
    def persist_with_live_evidence(
        recorder,
        scan: dict,
        records,
        *args,
        **kwargs,
    ):
        from mide import gs481_live_evidence_hard_bind as gs481

        provider, provider_source = gs427._active_provider()
        augmented = dict(scan)
        augmented["news_story_trace"] = gs481._news_truth()
        augmented["live_evidence_hard_bind"] = {
            "authority": LIVE_OBSERVABILITY_AUTHORITY,
            "provider_source": provider_source,
            "gs481_hard_bind": True,
            "trading_authority_changed": False,
        }
        gs481._attach_stream_failure(augmented, provider)
        return current(recorder, augmented, records, *args, **kwargs)

    setattr(persist_with_live_evidence, _LIVE_EVIDENCE_OWNER, True)
    persist_with_live_evidence._gs481_live_evidence_hard_bind = True
    persist_with_live_evidence._gs481_original = current
    globals_dict["persist_replayable_scan"] = persist_with_live_evidence
    if globals_dict is flight_recorder.__dict__:
        flight_recorder.persist_replayable_scan = persist_with_live_evidence


def _transport_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _transport_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def safe_transport_failure(event: Any) -> dict:
    """Return failure classification without persisting raw exception/URL text."""
    item = event if isinstance(event, dict) else {}
    raw = str(item.get("exception") or "")
    exception_type = raw.split(":", 1)[0].strip() if raw else None
    status_match = re.search(r"\b([45]\d\d)\b", raw)
    affected = sorted({
        str(symbol).strip().upper()
        for symbol in item.get("affected_symbols") or []
        if str(symbol or "").strip()
    })
    return {
        "provider": str(item.get("provider") or "Unknown")[:120],
        "operation": str(item.get("operation") or "unknown")[:120],
        "exception_type": exception_type[:80] if exception_type else None,
        "http_status": int(status_match.group(1)) if status_match else None,
        "affected_symbol_count": len(affected),
        "recovery_action": (
            str(item.get("recovery_action") or "")[:160] or None
        ),
        "raw_exception_persisted": False,
    }


def latest_transport_article_at(metrics: dict) -> str | None:
    newest = None
    for item in (metrics.get("newest_articles_by_symbol") or {}).values():
        if not isinstance(item, dict):
            continue
        stamp = item.get("newest_article_at")
        if stamp and (newest is None or str(stamp) > str(newest)):
            newest = str(stamp)
    return newest


def transport_truth(provider) -> dict:
    """Return bounded, credential-safe news transport provenance."""
    diagnostics = getattr(provider, "diagnostics", None)
    diagnostics = diagnostics if isinstance(diagnostics, dict) else {}
    metrics = diagnostics.get("news_coverage")
    metrics = metrics if isinstance(metrics, dict) else {}

    active_provider = str(metrics.get("active_provider") or "None")
    request_latencies = [
        value
        for raw in metrics.get("request_latency_ms") or []
        if (value := _transport_float(raw)) is not None
    ]
    requested = sorted({
        str(symbol).strip().upper()
        for symbol in metrics.get("requested_symbols") or []
        if str(symbol or "").strip()
    })
    with_articles = sorted({
        str(symbol).strip().upper()
        for symbol in metrics.get("symbols_with_articles") or []
        if str(symbol or "").strip()
    })
    without_articles = sorted({
        str(symbol).strip().upper()
        for symbol in metrics.get("symbols_without_articles") or []
        if str(symbol or "").strip()
    })
    failure_events = list(
        metrics.get("provider_failure_diagnostics") or []
    )
    provider_failures = _transport_int(metrics.get("provider_failures"))
    if failure_events:
        provider_failures = max(provider_failures, len(failure_events))

    requests_made = _transport_int(metrics.get("requests_made"))
    articles_received = _transport_int(metrics.get("articles_received"))
    if active_provider != "None":
        disposition = (
            "SUCCESS_WITH_ARTICLES"
            if articles_received
            else "SUCCESS_EMPTY"
        )
    elif provider_failures:
        disposition = "PROVIDER_FAILURE"
    elif requests_made:
        disposition = "NO_ACTIVE_PROVIDER"
    else:
        disposition = "NOT_OBSERVED"

    return {
        "authority": LIVE_OBSERVABILITY_AUTHORITY,
        "metrics_present": bool(metrics),
        "active_provider": active_provider,
        "fmp_active": active_provider == "Financial Modeling Prep news",
        "transport_disposition": disposition,
        "query_since": metrics.get("query_since"),
        "effective_provider_since": metrics.get("effective_provider_since"),
        "provider_endpoints": [
            str(value)[:120]
            for value in metrics.get("provider_endpoints") or []
        ],
        "requests_made": requests_made,
        "articles_received": articles_received,
        "provider_failure_count": provider_failures,
        "request_latency_last_ms": (
            request_latencies[-1] if request_latencies else None
        ),
        "request_latency_max_ms": (
            max(request_latencies) if request_latencies else None
        ),
        "last_successful_fetch": metrics.get("last_successful_fetch"),
        "newest_returned_article_at": latest_transport_article_at(metrics),
        "requested_symbol_count": len(requested),
        "requested_symbols": requested[:FMP_TRANSPORT_MAX_SYMBOLS],
        "symbols_with_articles_count": len(with_articles),
        "symbols_with_articles": with_articles[:FMP_TRANSPORT_MAX_SYMBOLS],
        "symbols_without_articles_count": len(without_articles),
        "symbols_without_articles": (
            without_articles[:FMP_TRANSPORT_MAX_SYMBOLS]
        ),
        "failure_tail": [
            safe_transport_failure(item)
            for item in failure_events[-FMP_TRANSPORT_MAX_FAILURES:]
        ],
        "raw_failure_text_persisted": False,
        "extra_provider_calls": 0,
        "trading_authority_changed": False,
    }


def install_fmp_transport_truth() -> None:
    """Enrich GS481 news truth with already-observed transport provenance."""
    from mide import gs427_flight_recorder_latency_hard_bind as gs427
    from mide import gs481_live_evidence_hard_bind as gs481

    current = gs481._news_truth
    if getattr(current, _FMP_TRANSPORT_OWNER, False):
        return

    @wraps(current)
    def news_truth_with_transport(*args, **kwargs):
        from mide import gs484_fmp_transport_truth as gs484

        truth = dict(current(*args, **kwargs) or {})
        provider, provider_source = gs427._active_provider()
        transport = gs484.transport_truth(provider)
        transport["provider_source"] = provider_source
        truth["transport"] = transport
        truth["gs484_transport_truth"] = True
        return truth

    setattr(news_truth_with_transport, _FMP_TRANSPORT_OWNER, True)
    news_truth_with_transport._gs484_fmp_transport_truth = True
    news_truth_with_transport._gs484_original = current
    gs481._news_truth = news_truth_with_transport


def retained_gs481_globals() -> list[dict[str, Any]]:
    """Return unique globals dicts used by reachable retained GS481 wrappers."""
    from mide import gs427_flight_recorder_latency_hard_bind as gs427
    from mide import gs481_live_evidence_hard_bind as gs481

    active_globals = gs427._active_recorder_globals()
    root = active_globals.get("persist_replayable_scan")
    candidates: list[dict[str, Any]] = []
    seen: set[int] = set()

    if callable(root):
        for function in gs427._walk_functions(root):
            globals_dict = getattr(function, "__globals__", None)
            if not isinstance(globals_dict, dict):
                continue
            is_gs481 = bool(
                getattr(
                    function,
                    "_gs481_live_evidence_hard_bind",
                    False,
                )
                or globals_dict.get("__name__")
                == "mide.gs481_live_evidence_hard_bind"
            )
            if (
                not is_gs481
                or not callable(globals_dict.get("_news_truth"))
            ):
                continue
            if id(globals_dict) not in seen:
                seen.add(id(globals_dict))
                candidates.append(globals_dict)

    current_globals = gs481.__dict__
    if (
        callable(current_globals.get("_news_truth"))
        and id(current_globals) not in seen
    ):
        candidates.append(current_globals)
    return candidates


def wrap_retained_news_truth(globals_dict: dict[str, Any]) -> bool:
    """Patch one exact retained GS481 function-global dictionary once."""
    from mide import gs427_flight_recorder_latency_hard_bind as gs427
    from mide import gs484_fmp_transport_truth as gs484

    current = globals_dict.get("_news_truth")
    if not callable(current):
        return False
    if getattr(current, _RETAINED_TRANSPORT_OWNER, False):
        return False

    @wraps(current)
    def retained_news_truth_with_transport(*args, **kwargs):
        truth = dict(current(*args, **kwargs) or {})
        provider, provider_source = gs427._active_provider()
        transport = gs484.transport_truth(provider)
        transport["provider_source"] = provider_source
        transport["retained_runtime_hard_bind"] = True
        truth["transport"] = transport
        truth["gs484_transport_truth"] = True
        truth["gs485_retained_transport_hard_bind"] = True
        return truth

    setattr(
        retained_news_truth_with_transport,
        _RETAINED_TRANSPORT_OWNER,
        True,
    )
    retained_news_truth_with_transport._gs485_retained_news_transport_hard_bind = True
    retained_news_truth_with_transport._gs485_original = current
    globals_dict["_news_truth"] = retained_news_truth_with_transport
    return True


def install_retained_news_transport_hard_bind() -> int:
    """Patch exact retained GS481 globals used by the active recorder graph."""
    return sum(
        wrap_retained_news_truth(globals_dict)
        for globals_dict in retained_gs481_globals()
    )


def top_level_news_transport(provider, provider_source: str) -> dict[str, Any]:
    from mide import gs484_fmp_transport_truth as gs484

    truth = dict(gs484.transport_truth(provider) or {})
    truth["provider_source"] = provider_source
    truth["top_level_hard_bind"] = True
    truth["extra_provider_calls"] = 0
    truth["trading_authority_changed"] = False
    return truth


def top_level_stream_transport(
    provider,
    provider_source: str,
) -> dict[str, Any]:
    from mide import gs481_live_evidence_hard_bind as gs481

    truth = dict(gs481._stream_failure_truth(provider) or {})
    truth["provider_source"] = provider_source
    truth["top_level_hard_bind"] = True
    truth["network_repair_attempted_here"] = False
    truth["trading_authority_changed"] = False
    return truth


def install_top_level_transport_truth() -> bool:
    """Bind overwrite-proof transport truth at the active persistence boundary."""
    from mide import flight_recorder
    from mide import gs427_flight_recorder_latency_hard_bind as gs427

    globals_dict = gs427._active_recorder_globals()
    current = globals_dict.get("persist_replayable_scan")
    if not callable(current):
        raise RuntimeError("Flight Recorder persistence callable is unavailable")
    if getattr(current, _TOP_LEVEL_TRANSPORT_OWNER, False):
        return False

    @wraps(current)
    def persist_with_top_level_transport(
        recorder,
        scan: dict,
        records,
        *args,
        **kwargs,
    ):
        from mide import gs486_top_level_transport_truth as gs486

        provider, provider_source = gs427._active_provider()
        augmented = dict(scan)
        augmented["news_transport_trace"] = gs486._news_transport(
            provider,
            provider_source,
        )
        augmented["stream_transport_trace"] = gs486._stream_transport(
            provider,
            provider_source,
        )
        augmented["transport_runtime_hard_bind"] = {
            "authority": LIVE_OBSERVABILITY_AUTHORITY,
            "gs486_top_level_transport_truth": True,
            "provider_source": provider_source,
            "trading_authority_changed": False,
        }
        return current(recorder, augmented, records, *args, **kwargs)

    setattr(
        persist_with_top_level_transport,
        _TOP_LEVEL_TRANSPORT_OWNER,
        True,
    )
    persist_with_top_level_transport._gs486_top_level_transport_truth = True
    persist_with_top_level_transport._gs486_original = current
    globals_dict["persist_replayable_scan"] = persist_with_top_level_transport
    if globals_dict is flight_recorder.__dict__:
        flight_recorder.persist_replayable_scan = (
            persist_with_top_level_transport
        )
    return True


# ---------------------------------------------------------------------------
# GS483 Flight Recorder read-side resource containment
# ---------------------------------------------------------------------------

RESOURCE_CONTAINMENT_AUTHORITY = "RESOURCE_CONTAINMENT_ONLY"
RESOURCE_TAIL_CHUNK_BYTES = 64 * 1024
_RESOURCE_CONTAINMENT_INSTALL_GENERATION = object()


def decode_recorder_json_line(raw: bytes):
    """Decode one JSONL row, skipping malformed/non-object content."""
    raw = raw.strip()
    if not raw:
        return None
    try:
        value = json.loads(raw.decode("utf-8", errors="ignore"))
    except (UnicodeError, ValueError, TypeError):
        return None
    return value if isinstance(value, dict) else None


def iter_valid_recorder_scans(path: Path) -> Iterator[dict]:
    """Stream valid JSONL records without materializing the whole recorder file."""
    if not path.exists():
        return
    with path.open("rb") as handle:
        for raw in handle:
            value = decode_recorder_json_line(raw)
            if value is not None:
                yield value


def bounded_latest_scan(
    path: Path,
    *,
    chunk_bytes: int = RESOURCE_TAIL_CHUNK_BYTES,
) -> dict | None:
    """Return the newest valid JSONL object using bounded reverse reads."""
    if not path.exists():
        return None
    try:
        size = path.stat().st_size
    except OSError:
        return None
    if size <= 0:
        return None

    chunk_bytes = max(1024, int(chunk_bytes))
    with path.open("rb") as handle:
        position = size
        carry = b""
        while position > 0:
            take = min(chunk_bytes, position)
            position -= take
            handle.seek(position)
            block = handle.read(take) + carry
            parts = block.split(b"\n")
            if position > 0:
                carry = parts.pop(0) if parts else block
            else:
                carry = b""
            for raw in reversed(parts):
                value = decode_recorder_json_line(raw)
                if value is not None:
                    return value
        if carry:
            return decode_recorder_json_line(carry)
    return None


def streaming_scans(path: Path) -> list[dict]:
    """Preserve FlightRecorder's historical list contract with lower transient memory."""
    return list(iter_valid_recorder_scans(path))


def streaming_symbol_history(path: Path, symbol: str) -> list[dict]:
    """Return one symbol's history without first materializing every scan."""
    wanted = str(symbol or "").strip().upper()
    if not wanted:
        return []
    history: list[dict] = []
    for scan in iter_valid_recorder_scans(path):
        symbol_path = next(
            (
                item
                for item in scan.get("symbols", [])
                if str(item.get("symbol", "")).upper() == wanted
            ),
            None,
        )
        if symbol_path:
            history.append(
                {
                    "scan_id": scan.get("scan_id"),
                    "timestamp": scan.get("timestamp"),
                    "scanner_version": scan.get("scanner_version"),
                    **symbol_path,
                }
            )
    return history


def recorder_resource_snapshot(recorder) -> dict:
    """Return small recorder/process metadata without reading recorder contents."""
    path = Path(recorder.path)
    try:
        file_bytes = int(path.stat().st_size) if path.exists() else 0
    except OSError:
        file_bytes = 0

    rss_mb = None
    try:
        import resource

        raw = float(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
        # Linux reports KiB; macOS reports bytes. Walter production is Linux.
        rss_mb = (
            round(raw / 1024.0, 1)
            if raw < 10_000_000
            else round(raw / (1024.0 * 1024.0), 1)
        )
    except Exception:
        pass

    return {
        "authority": RESOURCE_CONTAINMENT_AUTHORITY,
        "flight_recorder_bytes": file_bytes,
        "flight_recorder_mb": round(file_bytes / (1024.0 * 1024.0), 2),
        "process_max_rss_mb": rss_mb,
        "trading_logic_changed": False,
    }


def _inherit_resource_wrapper(wrapper, wrapped) -> None:
    for name, value in getattr(wrapped, "__dict__", {}).items():
        if name.startswith("_gs") and not hasattr(wrapper, name):
            setattr(wrapper, name, value)


def install_resource_containment() -> None:
    """Bind bounded FlightRecorder read helpers through Replay / Validation."""
    from mide.flight_recorder import FlightRecorder

    current_latest = FlightRecorder.latest_scan
    if (
        getattr(current_latest, "_gs483_install_generation", None)
        is not _RESOURCE_CONTAINMENT_INSTALL_GENERATION
    ):
        def latest_scan(self):
            return bounded_latest_scan(Path(self.path))

        _inherit_resource_wrapper(latest_scan, current_latest)
        latest_scan._gs483_resource_containment = True
        latest_scan._gs483_install_generation = (
            _RESOURCE_CONTAINMENT_INSTALL_GENERATION
        )
        latest_scan._gs483_original = current_latest
        FlightRecorder.latest_scan = latest_scan

    current_scans = FlightRecorder.scans
    if (
        getattr(current_scans, "_gs483_install_generation", None)
        is not _RESOURCE_CONTAINMENT_INSTALL_GENERATION
    ):
        def scans(self):
            return streaming_scans(Path(self.path))

        _inherit_resource_wrapper(scans, current_scans)
        scans._gs483_resource_containment = True
        scans._gs483_install_generation = (
            _RESOURCE_CONTAINMENT_INSTALL_GENERATION
        )
        scans._gs483_original = current_scans
        FlightRecorder.scans = scans

    current_history = FlightRecorder.history_for_symbol
    if (
        getattr(current_history, "_gs483_install_generation", None)
        is not _RESOURCE_CONTAINMENT_INSTALL_GENERATION
    ):
        def history_for_symbol(self, symbol: str):
            return streaming_symbol_history(Path(self.path), symbol)

        _inherit_resource_wrapper(history_for_symbol, current_history)
        history_for_symbol._gs483_resource_containment = True
        history_for_symbol._gs483_install_generation = (
            _RESOURCE_CONTAINMENT_INSTALL_GENERATION
        )
        history_for_symbol._gs483_original = current_history
        FlightRecorder.history_for_symbol = history_for_symbol



# ---------------------------------------------------------------------------
# GS464 session-aware VWAP parity replay labeling
# ---------------------------------------------------------------------------

_SESSION_VWAP_PARITY_OWNER = (
    "_walter_gs464_session_aware_vwap_parity_owner"
)


def install_session_aware_vwap_parity_labels() -> None:
    """Name GS464's decision policy in future Flight Recorder parity blocks."""
    from mide import gs391_webull_vwap_st_parity as gs391
    from mide import gs464_session_aware_vwap_parity as gs464

    current = gs391._build_scan_parity
    if getattr(
        current,
        _SESSION_VWAP_PARITY_OWNER,
        False,
    ):
        return

    @wraps(current)
    def build_scan_parity(records) -> dict:
        payload = dict(current(records) or {})
        payload["legacy_gs391_observation_policy"] = (
            gs391.PRIMARY_POLICY
        )
        payload["primary_vwap_policy"] = (
            gs464.SESSION_POLICY
        )
        for item in payload.get("symbols") or []:
            mode = item.get("vwap_anchor_mode")
            item["decision_vwap_policy"] = mode
            parity = item.get("parity")
            if isinstance(parity, dict):
                parity["decision_vwap_policy"] = mode
                parity["legacy_observation_policy"] = (
                    gs391.PRIMARY_POLICY
                )
        return payload

    for name, value in getattr(
        current,
        "__dict__",
        {},
    ).items():
        if name.startswith("_gs") and not hasattr(
            build_scan_parity,
            name,
        ):
            setattr(build_scan_parity, name, value)
    build_scan_parity._gs464_session_aware_vwap_parity = True
    build_scan_parity._gs464_original = current
    setattr(
        build_scan_parity,
        _SESSION_VWAP_PARITY_OWNER,
        True,
    )
    gs391._build_scan_parity = build_scan_parity



# ---------------------------------------------------------------------------
# GS470/GS471 live 30-second health replay persistence
# ---------------------------------------------------------------------------

def active_30s_recorder_globals() -> dict[str, Any]:
    try:
        from mide import gs427_flight_recorder_latency_hard_bind as gs427

        result = gs427._active_recorder_globals()
        if isinstance(result, dict):
            return result
    except Exception:
        pass
    from mide import flight_recorder

    return flight_recorder.__dict__


def install_30s_recorder_health() -> None:
    from mide import flight_recorder
    from mide import gs470_30s_activation_truth as gs470

    current = flight_recorder.persist_replayable_scan
    if getattr(current, gs470._RECORDER_OWNER, False):
        return

    @wraps(current)
    def persist_replayable_scan(
        recorder,
        scan: dict,
        records,
        *args,
        **kwargs,
    ):
        enriched = dict(scan or {})
        enriched["stream_30s_health"] = gs470.stream_30s_health(
            gs470._active_or_last_provider()
        )
        return current(
            recorder,
            enriched,
            records,
            *args,
            **kwargs,
        )

    persist_replayable_scan._gs470_30s_activation_truth = True
    persist_replayable_scan._gs470_original = current
    setattr(
        persist_replayable_scan,
        gs470._RECORDER_OWNER,
        True,
    )
    flight_recorder.persist_replayable_scan = (
        persist_replayable_scan
    )


def install_30s_hard_recorder_health() -> None:
    from mide import flight_recorder
    from mide import gs470_30s_activation_truth as gs470

    globals_dict = gs470._active_recorder_globals()
    current = globals_dict.get("persist_replayable_scan")
    if (
        not callable(current)
        or getattr(
            current,
            gs470._HARD_RECORDER_OWNER,
            False,
        )
    ):
        return

    @wraps(current)
    def persist_with_hard_bound_30s_health(
        recorder,
        scan: dict,
        records,
        *args,
        **kwargs,
    ):
        enriched = dict(scan or {})
        enriched["stream_30s_health"] = gs470.stream_30s_health(
            gs470._active_or_last_provider()
        )
        return current(
            recorder,
            enriched,
            records,
            *args,
            **kwargs,
        )

    persist_with_hard_bound_30s_health._gs471_30s_health_hard_bind = True
    persist_with_hard_bound_30s_health._gs471_original = current
    setattr(
        persist_with_hard_bound_30s_health,
        gs470._HARD_RECORDER_OWNER,
        True,
    )
    globals_dict["persist_replayable_scan"] = (
        persist_with_hard_bound_30s_health
    )
    if globals_dict is flight_recorder.__dict__:
        flight_recorder.persist_replayable_scan = (
            persist_with_hard_bound_30s_health
        )


def install_production_30s_replay_validation() -> None:
    install_30s_recorder_health()
    install_30s_hard_recorder_health()


__all__ = [
    "install_production_30s_replay_validation",
    "install_30s_recorder_health",
    "install_30s_hard_recorder_health",
    "active_30s_recorder_globals",
    "install_session_aware_vwap_parity_labels",
    "install_latency_truth_recorder",
    "build_latency_truth",
    "latency_provider_from_trace",
    "append_latency_history_event",
    "reset_latency_trace",
    "latency_trace_events",
    "latency_history_diagnostics",
    "normalize_latency_symbols",
    "LATENCY_TRUTH_AUTHORITY",
    "install_resource_containment",
    "recorder_resource_snapshot",
    "streaming_symbol_history",
    "streaming_scans",
    "bounded_latest_scan",
    "iter_valid_recorder_scans",
    "decode_recorder_json_line",
    "RESOURCE_CONTAINMENT_AUTHORITY",
    "RESOURCE_TAIL_CHUNK_BYTES",
    "install_top_level_transport_truth",
    "top_level_stream_transport",
    "top_level_news_transport",
    "install_retained_news_transport_hard_bind",
    "wrap_retained_news_truth",
    "retained_gs481_globals",
    "install_fmp_transport_truth",
    "transport_truth",
    "install_live_evidence_hard_bind",
    "attach_stream_failure",
    "stream_failure_truth",
    "live_news_truth",
    "LIVE_OBSERVABILITY_AUTHORITY",
    "install_benzinga_breaking_news_trace",
    "benzinga_breaking_news_recorder_wrapper",
    "benzinga_breaking_news_trace_snapshot",
    "install_catalyst_story_trace",
    "catalyst_story_recorder_wrapper",
    "catalyst_story_trace_snapshots",
    "FlightRecorder",
    "install_ignition_validation_sequence",
    "build_validation_sequence_with_ignition",
    "MissionOutcomeStore",
    "prefilter_decision",
    "scan_integrity_report",
]

"""Authoritative Walter Next Replay / Validation boundary.

Stable recorder/outcome classes remain direct imports. Replaceable validation
functions resolve dynamically so warm Streamlit reruns cannot retain stale wrappers.
"""

from __future__ import annotations

from copy import deepcopy
from functools import wraps

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


__all__ = [
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

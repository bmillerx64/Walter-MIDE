"""GS393: align operator ignition with live Webull behavior and decay stale extreme banners.

Live validation on 2026-09-08 showed two operator-truth failures:

1. Walter's GS348 attention path treated a literal SuperTrend-line/VWAP-line cross as
   ignition.  On GCDT the useful move began much earlier: price reclaimed/held VWAP
   while the 1-minute SuperTrend turned bullish.  Waiting for the lagging ST line to
   physically cross VWAP caused Walter to miss the actionable chart-review window.
2. GS333 intentionally pinned +75% extreme movers above ordinary states with no TTL,
   so a correctly-labeled DO NOT CHASE event could monopolize the top sightline for
   many minutes while fresher DEVELOPING/LOOK NOW setups formed below it.

GS393 changes operator attention/alert semantics only.  It does not change discovery,
market-data requests, ranking, qualification, readiness, entry thresholds, execution,
or orders.  The anti-chase VWAP rule remains authoritative.  Literal ST-line/VWAP
crosses remain available as secondary maturation evidence in GS378/GS390.
"""
from __future__ import annotations

from copy import deepcopy
from time import monotonic
from typing import Any

IGNITION_MAX_VWAP_DISTANCE_PCT = 2.0
IGNITION_FLIP_RECENT_SECONDS = 150.0
IGNITION_RECLAIM_RECENT_BARS = 2
EXTREME_DO_NOT_CHASE_TOP_TTL_SECONDS = 180.0

_extreme_first_seen: dict[str, float] = {}


def _number(record: dict, *keys: str, default: float | None = None) -> float | None:
    for key in keys:
        value = record.get(key)
        if value is None or value == "":
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return default


def _attention(record: dict) -> tuple[str, ...]:
    try:
        from .gs309_current_attention_mission import current_attention_provenance

        return tuple(current_attention_provenance(record))
    except Exception:
        return ()


def _fresh_catalyst(record: dict) -> bool:
    if any(
        bool(record.get(key))
        for key in (
            "fresh_news",
            "news_catalyst",
            "has_catalyst",
            "catalyst_confirmed",
        )
    ):
        return True
    if str(record.get("headline") or "").strip():
        return True
    return "FRESH_NEWS_SEED" in set(_attention(record))


def _one_minute_state(record: dict) -> dict:
    states = record.get("timeframes") or {}
    value = states.get("1m") if isinstance(states, dict) else None
    return dict(value) if isinstance(value, dict) else {}


def _three_minute_state(record: dict) -> dict:
    states = record.get("timeframes") or {}
    value = states.get("3m") if isinstance(states, dict) else None
    return dict(value) if isinstance(value, dict) else {}


def _supporting_flow(record: dict) -> tuple[bool, list[str]]:
    evidence: list[str] = []
    volume_accel = _number(record, "volume_acceleration", default=0.0) or 0.0
    dollar_flow = _number(record, "dollar_flow_acceleration", default=0.0) or 0.0
    participation = _number(
        record,
        "participation_score",
        "participation_surge_score",
        default=0.0,
    ) or 0.0
    expansion = _number(record, "expansion_score", "expansion_quality", default=0.0) or 0.0

    if volume_accel >= 1.0:
        evidence.append(f"volume acceleration {volume_accel:.2f}x")
    if dollar_flow >= 1.25:
        evidence.append(f"dollar-flow acceleration {dollar_flow:.2f}x")
    if participation >= 20.0:
        evidence.append(f"participation {participation:.0f}")
    if expansion >= 40.0:
        evidence.append(f"expansion {expansion:.0f}")
    if _fresh_catalyst(record):
        evidence.append("fresh catalyst")
    if _attention(record):
        evidence.append("current market attention")
    return bool(evidence), evidence


def ignition_evidence(record: dict) -> dict:
    """Return the operator ignition truth from already-computed Stage-6 evidence.

    Primary ignition is *not* a lagging ST-line/VWAP-line intersection.  It is a
    fresh 1m bullish SuperTrend state occurring with a fresh VWAP reclaim/hold, or a
    fresh 1m bullish ST flip while price is already above VWAP.  3m remains
    confirmation, never permission to begin chart review.
    """
    relation = str(record.get("vwap_relation") or "").strip().lower()
    distance = _number(record, "vwap_distance_pct")
    one = _one_minute_state(record)
    three = _three_minute_state(record)

    above = relation == "above" and distance is not None and distance >= 0.0
    inside_chase_guard = bool(
        above and distance is not None and distance <= IGNITION_MAX_VWAP_DISTANCE_PCT
    )
    one_bullish = bool(one.get("supertrend"))
    one_above_vwap = bool(one.get("above_vwap"))

    reclaim_age = _number(record, "vwap_reclaim_age_bars", default=999.0) or 999.0
    reclaim_recent = bool(
        record.get("vwap_reclaimed_last_10m")
        and reclaim_age <= IGNITION_RECLAIM_RECENT_BARS
    )
    flip_age = _number(record, "supertrend_flip_age_seconds")
    flip_recent = bool(
        flip_age is not None and 0.0 <= flip_age <= IGNITION_FLIP_RECENT_SECONDS
    )

    supported, support = _supporting_flow(record)
    trigger = None
    if inside_chase_guard and one_bullish and one_above_vwap and supported:
        if reclaim_recent:
            trigger = "VWAP_RECLAIM_WITH_BULLISH_1M_ST"
        elif flip_recent:
            trigger = "BULLISH_1M_ST_FLIP_ABOVE_VWAP"

    recent = trigger is not None
    return {
        "recent": recent,
        "trigger": trigger,
        "vwap_relation": relation,
        "vwap_distance_pct": distance,
        "inside_chase_guard": inside_chase_guard,
        "one_minute_supertrend_bullish": one_bullish,
        "one_minute_above_vwap": one_above_vwap,
        "vwap_reclaim_recent": reclaim_recent,
        "vwap_reclaim_age_bars": reclaim_age,
        "one_minute_bullish_flip_recent": flip_recent,
        "one_minute_bullish_flip_age_seconds": flip_age,
        "three_minute_confirmation": bool(
            three.get("supertrend") and three.get("above_vwap")
        ),
        "supporting_flow": support,
        "literal_st_line_vwap_cross_is_secondary": True,
    }


def _state_with_ignition(original, record: dict) -> dict:
    from . import gs310_unified_opportunity_state as unified

    base = original(record)
    evidence = ignition_evidence(record)
    if not evidence["recent"]:
        return base
    if base.get("state") in {
        unified.WATCH_FOR_ENTRY,
        unified.CHASE_WAIT,
        unified.HALTED,
    }:
        return base

    view = deepcopy(base)
    view["state"] = unified.LOOK_NOW
    view["color"] = unified.STATE_COLORS[unified.LOOK_NOW]
    trigger = evidence.get("trigger")
    if trigger == "VWAP_RECLAIM_WITH_BULLISH_1M_ST":
        view["reason"] = (
            "1m ignition: price freshly reclaimed/held VWAP while 1m SuperTrend is bullish."
        )
    else:
        view["reason"] = (
            "1m ignition: SuperTrend turned bullish while price is holding above VWAP."
        )
    view["next_step"] = (
        "Open the chart now. 3m confirmation may follow, but it is not required for "
        "chart review; do not chase if price extends beyond the VWAP guard."
    )
    provenance = list(view.get("attention_provenance") or [])
    if "FRESH_1M_IGNITION" not in provenance:
        provenance.append("FRESH_1M_IGNITION")
    view["attention_provenance"] = provenance
    return view


def _install_ignition_state() -> None:
    from . import gs310_unified_opportunity_state as unified
    from . import gs311_unified_voice as voice
    from . import gs314_state_consistency as consistency
    from . import gs363_operator_attention_hierarchy as hierarchy

    current = unified.opportunity_state
    if getattr(current, "_gs393_ignition_truth", False):
        calibrated = current
    else:
        original = current

        def calibrated(record: dict) -> dict:
            return _state_with_ignition(original, record)

        for name, value in getattr(current, "__dict__", {}).items():
            if name.startswith("_gs") and not hasattr(calibrated, name):
                setattr(calibrated, name, value)
        calibrated._gs393_ignition_truth = True
        calibrated._gs393_original = original
        unified.opportunity_state = calibrated

    # Keep every imported trader-facing binding on the same canonical state truth.
    voice.opportunity_state = calibrated
    consistency.opportunity_state = calibrated
    hierarchy.opportunity_state = calibrated


def _install_extreme_banner_decay() -> None:
    """Keep a new extreme event prominent briefly; stop pinning stale DO NOT CHASE."""
    from . import gs333_extreme_mover_operator_priority as extreme

    current = extreme.prioritized_extreme_event
    if getattr(current, "_gs393_extreme_decay", False):
        return

    def prioritized_with_decay(records, *, now: float | None = None):
        stamp = monotonic() if now is None else float(now)
        rows = list(records or [])
        extreme_symbols: set[str] = set()
        choices: list[tuple[tuple, dict, dict]] = []

        for record in rows:
            event = extreme.extreme_market_event(record)
            if not event:
                continue
            symbol = str(event.get("symbol") or "").upper()
            if not symbol:
                continue
            extreme_symbols.add(symbol)
            _extreme_first_seen.setdefault(symbol, stamp)

            label = str(event.get("label") or "").upper()
            elapsed = max(0.0, stamp - _extreme_first_seen[symbol])
            # HALTED and near-VWAP LOOK NOW remain immediate market events.  A far-
            # extended DO NOT CHASE banner gets a short top-of-screen TTL, then the
            # symbol remains visible through ordinary CHASE/WAIT and event lanes.
            eligible = (
                "HALTED" in label
                or "LOOK NOW" in label
                or elapsed <= EXTREME_DO_NOT_CHASE_TOP_TTL_SECONDS
            )
            if not eligible:
                continue

            dollar_volume = _number(record, "dollar_volume", default=0.0) or 0.0
            choices.append(
                (
                    (
                        1 if event.get("halted") else 0,
                        float(event.get("pct_change") or 0.0),
                        dollar_volume,
                    ),
                    record,
                    event,
                )
            )

        # If a symbol falls out of the extreme set, a later re-entry is a fresh event.
        for symbol in list(_extreme_first_seen):
            if symbol not in extreme_symbols:
                _extreme_first_seen.pop(symbol, None)

        if not choices:
            return None, None
        _, record, event = max(choices, key=lambda item: item[0])
        return record, event

    prioritized_with_decay._gs393_extreme_decay = True
    prioritized_with_decay._gs393_original = current
    extreme.prioritized_extreme_event = prioritized_with_decay


def _install_recorder_truth() -> None:
    """Add primary ignition semantics while retaining literal line-cross evidence."""
    from . import gs390_st_vwap_validation_sequence as sequence

    current = sequence.build_validation_sequence
    if getattr(current, "_gs393_ignition_truth", False):
        return

    def build_with_ignition(scan: dict, records, provider) -> dict:
        payload = current(scan, records, provider)
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
            ignition = ignition_evidence(record)
            if not ignition.get("recent") and symbol not in by_symbol:
                continue

            row = by_symbol.get(symbol)
            if row is None:
                one = sequence._event(record, "1m")
                three = sequence._event(record, "3m")
                row = {
                    "symbol": symbol,
                    "scan_price": _number(record, "price"),
                    "participation_score": _number(record, "participation_score"),
                    "participation_surge_score": _number(
                        record, "participation_surge_score"
                    ),
                    "volume_pace_ratio": _number(record, "volume_pace_ratio"),
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

    build_with_ignition._gs393_ignition_truth = True
    build_with_ignition._gs393_original = current
    sequence.build_validation_sequence = build_with_ignition


def reset_state() -> None:
    """Test helper for deterministic extreme-banner timing."""
    _extreme_first_seen.clear()


def install() -> None:
    """Install after GS392 as the final live operator-truth boundary."""
    _install_ignition_state()
    _install_extreme_banner_decay()
    _install_recorder_truth()

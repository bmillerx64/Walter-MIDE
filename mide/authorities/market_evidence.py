"""Authority boundary for Market Evidence.

This component owns the seam where raw/derived market observations are assembled.
During Phase 1 it delegates to the current validated analyzers without changing
thresholds, formulas, ordering, or evidence semantics.
"""

from collections.abc import Iterable, Mapping
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone
from functools import wraps
import math
from statistics import median
from time import monotonic, time as epoch_time
from typing import Any, Callable

import pandas as pd

def analyze_candidates(*args, **kwargs):
    """Delegate to Walter's currently installed discovery analyzer."""
    from mide import discovery
    return discovery.analyze_candidates(*args, **kwargs)


def expansion_candidate_diagnostic(*args, **kwargs):
    """Delegate to Walter's currently installed expansion diagnostic."""
    from mide import decision_engine
    return decision_engine.expansion_candidate_diagnostic(*args, **kwargs)


def apply_scanner_v2(*args, **kwargs):
    """Delegate to Walter's currently installed Scanner V2 implementation."""
    from mide import scanner_v2
    return scanner_v2.apply_scanner_v2(*args, **kwargs)


def participation_gate_rejection_diagnostics(*args, **kwargs):
    from mide import scanner_v2
    return scanner_v2.participation_gate_rejection_diagnostics(*args, **kwargs)


def strengthening_diagnostics(*args, **kwargs):
    from mide import scanner_v2
    return scanner_v2.strengthening_diagnostics(*args, **kwargs)


# ---------------------------------------------------------------------------
# Native market-awareness evidence
# ---------------------------------------------------------------------------

EXTREME_MOVER_PCT = 75.0
MARKET_EVENT_LIMIT = 3

LIQUIDITY_TREND_MIN_GAIN_PCT = 30.0
LIQUIDITY_TREND_MIN_VOLUME = 50_000_000.0
LIQUIDITY_TREND_MAX_PRICE = 5.0
LIQUIDITY_TREND_MAX_RANK = 10
LIQUIDITY_TREND_LIMIT = 2

STRATEGY_LEADER_MIN_GAIN_PCT = 15.0
STRATEGY_LEADER_MAX_DAY_GAINER_RANK = 10
STRATEGY_LEADER_PRICE_CEILING = 5.0
STRATEGY_LEADER_LIMIT = 5

_LATEST_MARKET_EVENTS: list[dict] = []
_market_event_liquidity_stage_active = False
_MARKET_EVENT_CAPTURE_OWNER = "_walter_gs334_market_event_capture"
_STRATEGY_LEADER_CAPTURE_OWNER = "_walter_gs377_strategy_leader_awareness"


def _market_event_number(value, default: float | None = None) -> float | None:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def base_market_event_rows(
    native_rows: Iterable[dict] | None,
    *,
    threshold: float = EXTREME_MOVER_PCT,
    limit: int = MARKET_EVENT_LIMIT,
) -> list[dict]:
    """Return GS334 extraordinary Day Gainers as attention-only evidence."""
    events: list[dict] = []
    for source in native_rows or []:
        symbol = str(source.get("symbol") or "").strip().upper()
        sources = {str(value or "") for value in source.get("sources") or []}
        pct_change = _market_event_number(source.get("change_ratio"))
        if not symbol or "day_gainers" not in sources or pct_change is None:
            continue
        if pct_change < float(threshold):
            continue
        ranks = source.get("ranks") or {}
        rank = _market_event_number(ranks.get("day_gainers"), default=999.0) or 999.0
        events.append(
            {
                "symbol": symbol,
                "pct_change": round(pct_change, 2),
                "rank": int(rank),
                "price": _market_event_number(source.get("price")),
                "volume": _market_event_number(source.get("volume")),
                "sources": sorted(sources),
                "attention_only": True,
            }
        )
    events.sort(key=lambda row: (row["rank"], -row["pct_change"], row["symbol"]))
    return events[: max(0, int(limit))]


def high_liquidity_trend_rows(
    native_rows: Iterable[dict] | None,
    *,
    min_gain_pct: float = LIQUIDITY_TREND_MIN_GAIN_PCT,
    min_volume: float = LIQUIDITY_TREND_MIN_VOLUME,
    max_price: float = LIQUIDITY_TREND_MAX_PRICE,
    max_rank: int = LIQUIDITY_TREND_MAX_RANK,
    limit: int = LIQUIDITY_TREND_LIMIT,
) -> list[dict]:
    """Return GS340 GPRO-like liquid trends as attention-only evidence."""
    events: list[dict] = []
    for source in native_rows or []:
        symbol = str(source.get("symbol") or "").strip().upper()
        sources = {str(value or "") for value in source.get("sources") or []}
        pct_change = _market_event_number(source.get("change_ratio"))
        price = _market_event_number(source.get("price"))
        volume = _market_event_number(source.get("volume"))
        ranks = source.get("ranks") or {}
        rank = _market_event_number(ranks.get("day_gainers"), default=999.0) or 999.0

        if not symbol or "day_gainers" not in sources:
            continue
        if pct_change is None or pct_change < float(min_gain_pct):
            continue
        if pct_change >= EXTREME_MOVER_PCT:
            continue
        if price is None or price <= 0 or price > float(max_price):
            continue
        if volume is None or volume < float(min_volume):
            continue
        if rank > int(max_rank):
            continue

        events.append(
            {
                "symbol": symbol,
                "pct_change": round(pct_change, 2),
                "rank": int(rank),
                "price": price,
                "volume": volume,
                "sources": sorted(sources),
                "attention_only": True,
                "event_type": "high_liquidity_trend",
            }
        )

    events.sort(key=lambda row: (row["rank"], -row["pct_change"], row["symbol"]))
    return events[: max(0, int(limit))]


def market_event_rows(
    native_rows: Iterable[dict] | None,
    *,
    threshold: float = EXTREME_MOVER_PCT,
    limit: int = MARKET_EVENT_LIMIT,
) -> list[dict]:
    """Return the historical GS334 row contract plus activated GS340 evidence."""
    rows = list(native_rows or [])
    baseline = base_market_event_rows(rows, threshold=threshold, limit=limit)
    if not _market_event_liquidity_stage_active:
        return baseline

    extras = high_liquidity_trend_rows(rows)
    seen = {str(event.get("symbol") or "").upper() for event in baseline}
    combined = list(baseline)
    for event in extras:
        symbol = str(event.get("symbol") or "").upper()
        if symbol not in seen:
            combined.append(event)
            seen.add(symbol)
    return combined


def activate_high_liquidity_trend_watch() -> None:
    """Activate GS340 at its historical startup position without another wrapper."""
    global _market_event_liquidity_stage_active

    _market_event_liquidity_stage_active = True
    market_event_rows._gs340_high_liquidity_trend_watch = True


def completed_scan_market_events(state: Mapping[str, Any] | None) -> list[dict]:
    """Read the durable market-event snapshot from completed-scan diagnostics."""
    if not state:
        return []
    scan = state.get("completed_scan")
    if scan is None:
        context = state.get("scan_context")
        scan = getattr(context, "completed_scan", None) if context is not None else None
    diagnostics = getattr(scan, "diagnostics", None)
    if not isinstance(diagnostics, dict):
        return []
    lane = diagnostics.get("market_event_lane")
    if not isinstance(lane, dict):
        return []
    events = lane.get("events")
    if not isinstance(events, list):
        return []
    return [dict(event) for event in events if isinstance(event, dict)]


def _replace_latest_market_events(events: Iterable[dict] | None) -> None:
    _LATEST_MARKET_EVENTS.clear()
    _LATEST_MARKET_EVENTS.extend(
        dict(event)
        for event in events or []
        if isinstance(event, dict)
    )


def install_market_event_capture() -> None:
    """Capture GS334/GS340 awareness evidence from already-fetched native rows."""
    from mide import webull_connection as connection
    from mide.webull_live import LiveWebullProvider

    current_assets = LiveWebullProvider.assets
    if getattr(current_assets, _MARKET_EVENT_CAPTURE_OWNER, False):
        return

    @wraps(current_assets)
    def assets_with_market_events(self):
        _replace_latest_market_events([])
        assets = current_assets(self)
        native_rows = list(
            (getattr(self, "_native_radar_prices", {}) or {}).values()
        )
        events = market_event_rows(native_rows)
        _replace_latest_market_events(events)
        diagnostics = getattr(self, "diagnostics", None)
        if isinstance(diagnostics, dict):
            diagnostics["market_event_lane"] = {
                "source": "Webull native DAY_GAINERS",
                "threshold_pct": EXTREME_MOVER_PCT,
                "attention_only": True,
                "events": [dict(event) for event in events],
            }
        return assets

    assets_with_market_events._gs334_market_event_capture = True
    assets_with_market_events._gs334_original = current_assets
    setattr(assets_with_market_events, _MARKET_EVENT_CAPTURE_OWNER, True)
    LiveWebullProvider.assets = assets_with_market_events
    connection._webull_native_assets = assets_with_market_events


def implied_previous_close(
    price: float | None,
    pct_change: float | None,
) -> float | None:
    """Recover GS377's prior-close reference from the native Day Gainer row."""
    if price is None or pct_change is None:
        return None
    denominator = 1.0 + float(pct_change) / 100.0
    if price <= 0 or denominator <= 0:
        return None
    return float(price) / denominator


def strategy_leader_rows(
    native_rows: Iterable[dict] | None,
    *,
    min_gain_pct: float = STRATEGY_LEADER_MIN_GAIN_PCT,
    max_rank: int = STRATEGY_LEADER_MAX_DAY_GAINER_RANK,
    price_ceiling: float = STRATEGY_LEADER_PRICE_CEILING,
    limit: int = STRATEGY_LEADER_LIMIT,
) -> list[dict]:
    """Return GS377 strategy-relevant Day Gainers as attention-only evidence."""
    leaders: list[dict] = []
    for source in native_rows or []:
        symbol = str(source.get("symbol") or "").strip().upper()
        sources = {str(value or "") for value in source.get("sources") or []}
        if not symbol or "day_gainers" not in sources:
            continue

        pct_change = _market_event_number(source.get("change_ratio"))
        price = _market_event_number(source.get("price"))
        volume = _market_event_number(source.get("volume"))
        ranks = source.get("ranks") or {}
        rank = _market_event_number(ranks.get("day_gainers"), default=999.0) or 999.0
        if pct_change is None or pct_change < float(min_gain_pct):
            continue
        if rank > int(max_rank):
            continue

        prior_close = implied_previous_close(price, pct_change)
        currently_in_range = price is not None and 0 < price <= float(price_ceiling)
        launched_from_range = (
            prior_close is not None and 0 < prior_close <= float(price_ceiling)
        )
        if not (currently_in_range or launched_from_range):
            continue

        leaders.append(
            {
                "symbol": symbol,
                "pct_change": round(float(pct_change), 2),
                "rank": int(rank),
                "price": price,
                "volume": volume,
                "sources": sorted(sources),
                "attention_only": True,
                "event_type": "strategy_leader",
                "strategy_price_reference": (
                    "current_price"
                    if currently_in_range
                    else "implied_previous_close"
                ),
                "implied_previous_close": (
                    round(prior_close, 4) if prior_close is not None else None
                ),
            }
        )

    leaders.sort(key=lambda row: (row["rank"], -row["pct_change"], row["symbol"]))
    return leaders[: max(0, int(limit))]


def merge_strategy_leader_events(
    baseline_events: Iterable[dict] | None,
    native_rows: Iterable[dict] | None,
) -> list[dict]:
    combined = [
        dict(event)
        for event in baseline_events or []
        if isinstance(event, dict)
    ]
    seen = {
        str(event.get("symbol") or "").strip().upper()
        for event in combined
        if str(event.get("symbol") or "").strip()
    }
    for event in strategy_leader_rows(native_rows):
        symbol = str(event.get("symbol") or "").strip().upper()
        if not symbol or symbol in seen:
            continue
        combined.append(dict(event))
        seen.add(symbol)
    return combined


def publish_strategy_leader_awareness(
    provider,
    native_rows: Iterable[dict] | None,
) -> list[dict]:
    """Persist GS377's overlay into the same authoritative awareness snapshot."""
    diagnostics = getattr(provider, "diagnostics", None)
    lane_diagnostics = (
        diagnostics.get("market_event_lane")
        if isinstance(diagnostics, dict)
        else None
    )
    if isinstance(lane_diagnostics, dict):
        baseline = lane_diagnostics.get("events") or []
    else:
        baseline = _LATEST_MARKET_EVENTS

    combined = merge_strategy_leader_events(baseline, native_rows)
    _replace_latest_market_events(combined)

    if isinstance(diagnostics, dict):
        updated = dict(lane_diagnostics or {})
        updated.setdefault("source", "Webull native DAY_GAINERS")
        updated["attention_only"] = True
        updated["events"] = [dict(event) for event in combined]
        updated["strategy_leader_awareness"] = {
            "min_gain_pct": STRATEGY_LEADER_MIN_GAIN_PCT,
            "max_day_gainer_rank": STRATEGY_LEADER_MAX_DAY_GAINER_RANK,
            "price_ceiling": STRATEGY_LEADER_PRICE_CEILING,
            "limit": STRATEGY_LEADER_LIMIT,
        }
        diagnostics["market_event_lane"] = updated
    return combined


def install_strategy_leader_awareness() -> None:
    """Overlay GS377 after GS334/GS340 without changing provider-call count."""
    from mide import webull_connection as connection
    from mide.webull_live import LiveWebullProvider

    current_assets = LiveWebullProvider.assets
    if getattr(current_assets, _STRATEGY_LEADER_CAPTURE_OWNER, False):
        return

    @wraps(current_assets)
    def assets_with_strategy_leader_awareness(self):
        assets = current_assets(self)
        native_rows = list(
            (getattr(self, "_native_radar_prices", {}) or {}).values()
        )
        publish_strategy_leader_awareness(self, native_rows)
        return assets

    assets_with_strategy_leader_awareness._gs377_strategy_leader_awareness = True
    assets_with_strategy_leader_awareness._gs377_original = current_assets
    setattr(
        assets_with_strategy_leader_awareness,
        _STRATEGY_LEADER_CAPTURE_OWNER,
        True,
    )
    LiveWebullProvider.assets = assets_with_strategy_leader_awareness

    if getattr(connection, "_webull_native_assets", None) is current_assets:
        connection._webull_native_assets = assets_with_strategy_leader_awareness


IGNITION_MAX_VWAP_DISTANCE_PCT = 2.0
IGNITION_FLIP_RECENT_SECONDS = 150.0
IGNITION_RECLAIM_RECENT_BARS = 2


def _ignition_number(
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


def _ignition_attention(record: dict) -> tuple[str, ...]:
    try:
        from mide.gs309_current_attention_mission import current_attention_provenance

        return tuple(current_attention_provenance(record))
    except Exception:
        return ()


def _ignition_fresh_catalyst(record: dict) -> bool:
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
    return "FRESH_NEWS_SEED" in set(_ignition_attention(record))


def _ignition_timeframe_state(record: dict, label: str) -> dict:
    states = record.get("timeframes") or {}
    value = states.get(label) if isinstance(states, dict) else None
    return dict(value) if isinstance(value, dict) else {}


def _ignition_supporting_flow(record: dict) -> tuple[bool, list[str]]:
    evidence: list[str] = []
    volume_accel = _ignition_number(record, "volume_acceleration", default=0.0) or 0.0
    dollar_flow = _ignition_number(
        record,
        "dollar_flow_acceleration",
        default=0.0,
    ) or 0.0
    participation = _ignition_number(
        record,
        "participation_score",
        "participation_surge_score",
        default=0.0,
    ) or 0.0
    expansion = _ignition_number(
        record,
        "expansion_score",
        "expansion_quality",
        default=0.0,
    ) or 0.0

    if volume_accel >= 1.0:
        evidence.append(f"volume acceleration {volume_accel:.2f}x")
    if dollar_flow >= 1.25:
        evidence.append(f"dollar-flow acceleration {dollar_flow:.2f}x")
    if participation >= 20.0:
        evidence.append(f"participation {participation:.0f}")
    if expansion >= 40.0:
        evidence.append(f"expansion {expansion:.0f}")
    if _ignition_fresh_catalyst(record):
        evidence.append("fresh catalyst")
    if _ignition_attention(record):
        evidence.append("current market attention")
    return bool(evidence), evidence


def ignition_evidence(record: dict) -> dict:
    """Return GS393 primary 1m ignition truth from already-computed market evidence."""
    relation = str(record.get("vwap_relation") or "").strip().lower()
    distance = _ignition_number(record, "vwap_distance_pct")
    one = _ignition_timeframe_state(record, "1m")
    three = _ignition_timeframe_state(record, "3m")

    above = relation == "above" and distance is not None and distance >= 0.0
    inside_chase_guard = bool(
        above and distance is not None and distance <= IGNITION_MAX_VWAP_DISTANCE_PCT
    )
    one_bullish = bool(one.get("supertrend"))
    one_above_vwap = bool(one.get("above_vwap"))

    reclaim_age = (
        _ignition_number(record, "vwap_reclaim_age_bars", default=999.0) or 999.0
    )
    reclaim_recent = bool(
        record.get("vwap_reclaimed_last_10m")
        and reclaim_age <= IGNITION_RECLAIM_RECENT_BARS
    )
    flip_age = _ignition_number(record, "supertrend_flip_age_seconds")
    flip_recent = bool(
        flip_age is not None and 0.0 <= flip_age <= IGNITION_FLIP_RECENT_SECONDS
    )

    supported, support = _ignition_supporting_flow(record)
    trigger = None
    if inside_chase_guard and one_bullish and one_above_vwap and supported:
        if reclaim_recent:
            trigger = "VWAP_RECLAIM_WITH_BULLISH_1M_ST"
        elif flip_recent:
            trigger = "BULLISH_1M_ST_FLIP_ABOVE_VWAP"

    return {
        "recent": trigger is not None,
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


RETEST_TRUTH_AUTHORITY = "PRESENTATION_GUARDRAIL_ONLY"
RETEST_MEMORY_AUTHORITY = "PRESENTATION_MEMORY_ONLY"
_RETEST_MEMORY_BUILD_OWNER = "_walter_gs514_retest_event_memory_build"
_RETEST_MEMORY_TRUTH_OWNER = "_walter_gs514_retest_event_memory_truth"


def _near_st_line_pct() -> float:
    from mide.gs462_preflip_ignition_watch import NEAR_ST_LINE_PCT

    return float(NEAR_ST_LINE_PCT)


def _number_value(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if pd.isna(number):
        return None
    return number


def _decision_evidence(record: dict) -> dict:
    value = record.get("decision_time_evidence") or {}
    return value if isinstance(value, dict) else {}


def _evidence_field(record: dict, key: str, default=None):
    if key in record and record.get(key) is not None:
        return record.get(key)
    return _decision_evidence(record).get(key, default)


def base_three_minute_st_retest_truth(record: dict) -> dict:
    """Return current 3m SuperTrend proximity/loss truth from existing evidence."""
    from mide.gs462_preflip_ignition_watch import _timeframe_detail

    source = record
    if not isinstance(record.get("timeframes"), dict):
        decision = _decision_evidence(record)
        if isinstance(decision.get("timeframes"), dict):
            source = dict(decision)
            source.update(record)
            source["timeframes"] = decision["timeframes"]

    detail = _timeframe_detail(source, "3m")
    price = _number_value(_evidence_field(record, "price"))
    st_value = _number_value(detail.get("current_supertrend"))
    bullish = bool(detail.get("bullish"))
    available = bool(detail.get("available") and price is not None and st_value is not None)

    signed_gap = None
    if available and price not in (None, 0):
        signed_gap = (price - st_value) / price * 100.0

    state = "UNAVAILABLE"
    near_limit = _near_st_line_pct()
    if available:
        if not bullish or (signed_gap is not None and signed_gap < 0.0):
            state = "3M_ST_LOST"
        elif signed_gap is not None and signed_gap <= near_limit:
            state = "ST_RETEST_CONFIRMED"
        else:
            state = "NOT_AT_3M_ST_YET"

    return {
        "available": available,
        "state": state,
        "price": price,
        "three_minute_supertrend": st_value,
        "signed_gap_pct": round(signed_gap, 3) if signed_gap is not None else None,
        "near_st_line_limit_pct": near_limit,
        "three_minute_bullish": bullish,
        "authority": RETEST_TRUTH_AUTHORITY,
        "entry_authority_changed": False,
        "readiness_authority_changed": False,
    }


# Public evidence seam. GS514 compatibility installation may wrap this callable with
# held-retest memory, but the current-price truth above remains the authoritative base.
three_minute_st_retest_truth = base_three_minute_st_retest_truth


def latest_held_retest(
    tf: pd.DataFrame,
    st_line: pd.Series,
    trend: pd.Series,
    *,
    observed_at: pd.Timestamp,
) -> dict:
    """Return the latest held retest inside the current uninterrupted bullish run."""
    if tf is None or tf.empty or st_line is None or trend is None:
        return {
            "available": False,
            "active_memory": False,
            "authority": RETEST_MEMORY_AUTHORITY,
        }

    common = tf.index.intersection(st_line.index).intersection(trend.index)
    if len(common) == 0:
        return {
            "available": False,
            "active_memory": False,
            "authority": RETEST_MEMORY_AUTHORITY,
        }

    frame = tf.loc[common]
    st = st_line.loc[common]
    bullish = trend.loc[common].fillna(False).astype(bool)
    if not bool(bullish.iloc[-1]):
        return {
            "available": False,
            "active_memory": False,
            "invalidated": True,
            "invalidation_reason": "current 3m SuperTrend is bearish",
            "authority": RETEST_MEMORY_AUTHORITY,
        }

    last_false_position = -1
    for position, value in enumerate(bullish.tolist()):
        if not value:
            last_false_position = position
    run_start_position = last_false_position + 1

    lows = pd.to_numeric(frame["low"], errors="coerce")
    closes = pd.to_numeric(frame["close"], errors="coerce")
    st_numeric = pd.to_numeric(st, errors="coerce")

    valid = bullish & lows.notna() & closes.notna() & st_numeric.notna() & (st_numeric > 0)
    low_gap_pct = (lows - st_numeric) / st_numeric * 100.0
    held = (
        valid
        & (low_gap_pct.abs() <= _near_st_line_pct())
        & (closes >= st_numeric)
    )
    if run_start_position > 0:
        held.iloc[:run_start_position] = False

    hits = list(held[held].index)
    if not hits:
        return {
            "available": False,
            "active_memory": False,
            "current_three_minute_bullish": True,
            "bullish_run_start_timestamp": common[run_start_position].isoformat(),
            "near_st_line_limit_pct": _near_st_line_pct(),
            "authority": RETEST_MEMORY_AUTHORITY,
        }

    stamp = hits[-1]
    position = common.get_loc(stamp)
    low = _number_value(lows.loc[stamp])
    close = _number_value(closes.loc[stamp])
    retest_st = _number_value(st_numeric.loc[stamp])
    signed_low_gap = _number_value(low_gap_pct.loc[stamp])

    current_close = _number_value(closes.iloc[-1])
    current_st = _number_value(st_numeric.iloc[-1])
    current_bullish = bool(bullish.iloc[-1])
    active_memory = bool(
        current_bullish
        and current_close is not None
        and current_st is not None
        and current_close >= current_st
    )
    age_seconds = max(
        0.0,
        (pd.Timestamp(observed_at) - pd.Timestamp(stamp)).total_seconds(),
    )
    current_gap = (
        (current_close - current_st) / current_st * 100.0
        if current_close is not None and current_st not in (None, 0)
        else None
    )

    from mide import gs421_multitimeframe_convergence_recorder as gs421

    return {
        "available": True,
        "active_memory": active_memory,
        "timestamp": pd.Timestamp(stamp).isoformat(),
        "age_seconds": round(age_seconds, 1),
        "bars_since_retest": max(0, len(common) - 1 - int(position)),
        "retest_low": low,
        "retest_close": close,
        "supertrend_at_retest": retest_st,
        "signed_low_gap_pct": round(signed_low_gap, 3) if signed_low_gap is not None else None,
        "current_close": current_close,
        "current_supertrend": current_st,
        "current_gap_pct": round(current_gap, 3) if current_gap is not None else None,
        "current_three_minute_bullish": current_bullish,
        "current_bar_is_retest": bool(stamp == common[-1]),
        "bullish_run_start_timestamp": common[run_start_position].isoformat(),
        "near_st_line_limit_pct": _near_st_line_pct(),
        "source": gs421.SOURCE,
        "authority": RETEST_MEMORY_AUTHORITY,
        "entry_authority_changed": False,
        "readiness_authority_changed": False,
        "ranking_changed": False,
        "audio_changed": False,
    }


def reconstruct_three_minute_retest(raw_rows, client) -> dict:
    """Reconstruct held-retest memory from already-captured current-session bars."""
    try:
        from mide import gs378_live_vwap_st_crossover as gs378
        from mide import gs421_multitimeframe_convergence_recorder as gs421
        from mide.indicators import supertrend

        frame = client.bars_frame(raw_rows or [])
        context = gs378.primary_vwap_context(frame)
        day = context.get("day")
        if day is None or day.empty:
            return {
                "available": False,
                "active_memory": False,
                "authority": RETEST_MEMORY_AUTHORITY,
            }
        tf = gs421._timeframe_frame(day, "3m")
        if tf is None or tf.empty:
            return {
                "available": False,
                "active_memory": False,
                "authority": RETEST_MEMORY_AUTHORITY,
            }
        st_line, trend = supertrend(tf, 10, 3)
        observed_at = pd.Timestamp(day.index[-1])
        return latest_held_retest(tf, st_line, trend, observed_at=observed_at)
    except Exception as exc:
        return {
            "available": False,
            "active_memory": False,
            "error_type": type(exc).__name__,
            "authority": RETEST_MEMORY_AUTHORITY,
        }


def retest_event_from_record(record: dict) -> dict:
    maturation = record.get("multitimeframe_maturation") or {}
    if not isinstance(maturation, dict):
        return {}
    event = maturation.get("three_minute_st_retest_event") or {}
    return event if isinstance(event, dict) else {}


def memory_adjusted_retest_truth(original, record: dict) -> dict:
    """Let a valid held-retest event override current proximity-only wording."""
    truth = dict(original(record))
    event = retest_event_from_record(record)
    if (
        truth.get("state") in {"NOT_AT_3M_ST_YET", "ST_RETEST_CONFIRMED"}
        and event.get("available")
        and event.get("active_memory")
    ):
        truth["state"] = "PRIOR_ST_RETEST_HELD"
        truth["prior_retest_event"] = dict(event)
        truth["authority"] = RETEST_MEMORY_AUTHORITY
        truth["entry_authority_changed"] = False
        truth["readiness_authority_changed"] = False
    return truth


def install_retest_event_memory() -> None:
    """Attach held-retest reconstruction and memory to the Market Evidence seam."""
    from mide import gs421_multitimeframe_convergence_recorder as gs421

    current_build = gs421.build_maturation_evidence
    if not getattr(current_build, _RETEST_MEMORY_BUILD_OWNER, False):
        @wraps(current_build)
        def build_with_retest(record: dict, raw_rows, client) -> dict:
            evidence = current_build(record, raw_rows, client)
            if not isinstance(evidence, dict) or evidence.get("skipped"):
                return evidence
            updated = dict(evidence)
            updated["three_minute_st_retest_event"] = reconstruct_three_minute_retest(
                raw_rows,
                client,
            )
            updated["three_minute_st_retest_memory_authority"] = RETEST_MEMORY_AUTHORITY
            return updated

        setattr(build_with_retest, _RETEST_MEMORY_BUILD_OWNER, True)
        build_with_retest._gs514_original = current_build
        gs421.build_maturation_evidence = build_with_retest

    global three_minute_st_retest_truth
    current_truth = three_minute_st_retest_truth
    if not getattr(current_truth, _RETEST_MEMORY_TRUTH_OWNER, False):
        @wraps(current_truth)
        def truth_with_memory(record: dict) -> dict:
            return memory_adjusted_retest_truth(current_truth, record)

        setattr(truth_with_memory, _RETEST_MEMORY_TRUTH_OWNER, True)
        truth_with_memory._gs514_original = current_truth
        three_minute_st_retest_truth = truth_with_memory


PROVEN_LEADER_EXTENSION_PCT = 5.0
NEAR_VWAP_WINDOW_PCT = 2.0
LEADER_MEMORY_TTL_SECONDS = 90 * 60.0
MIN_LEADER_PARTICIPATION = 20.0
MIN_LEADER_VOLUME_ACCELERATION = 1.0
MIN_LEADER_DOLLAR_FLOW_ACCELERATION = 1.25
MAX_REIGNITION_VWAP_DISTANCE_PCT = 5.0

RESET_WATCH = "RESET_WATCH"
REIGNITION = "REIGNITION"
THREE_MINUTE_CONFIRMATION = "THREE_MINUTE_CONFIRMATION"
LEADER_RESET_AUTHORITY = "OPERATOR_ATTENTION_ONLY"


@dataclass
class LeaderMemory:
    extended_at: float
    last_seen_at: float
    max_vwap_distance_pct: float
    peak_pct_change: float | None
    extension_price: float | None
    stage: str = "NONE"
    transition_marker: str | None = None


_leader_memory: dict[str, LeaderMemory] = {}


def _leader_number(value: Any) -> float | None:
    try:
        return float(value) if value is not None and value != "" else None
    except (TypeError, ValueError):
        return None


def _leader_decision(record: dict) -> dict:
    value = record.get("decision_time_evidence") or {}
    return value if isinstance(value, dict) else {}


def _leader_field(record: dict, key: str, default=None):
    if key in record and record.get(key) is not None:
        return record.get(key)
    return _leader_decision(record).get(key, default)


def _leader_timeframes(record: dict) -> dict:
    value = _leader_field(record, "timeframes", {})
    return value if isinstance(value, dict) else {}


def _leader_tf(record: dict, label: str) -> dict:
    detail = _leader_timeframes(record).get(label) or {}
    if not isinstance(detail, dict):
        return {"bullish": False, "above_vwap": False, "available": False}
    bullish = bool(
        detail.get("current_supertrend_bullish")
        if "current_supertrend_bullish" in detail
        else detail.get("supertrend_bullish", detail.get("supertrend"))
    )
    above = bool(
        detail.get("current_above_vwap")
        if "current_above_vwap" in detail
        else detail.get("above_vwap")
    )
    return {
        "bullish": bullish,
        "above_vwap": above,
        "available": detail.get("data_available") is not False and bool(detail),
    }


def _current_webull_mover(record: dict) -> bool:
    reasons = " | ".join(
        str(value or "")
        for value in _leader_field(record, "discovery_reasons", []) or []
    )
    return bool(
        "Webull native: day_gainers" in reasons
        or "Webull native: five_minute_movers" in reasons
    )


def _leader_fresh_source(record: dict) -> bool:
    from mide.gs373_operator_visibility_freshness import MAX_OPERATOR_BAR_AGE_SECONDS

    age = _leader_number(
        _leader_field(
            record,
            "source_bar_age_seconds",
            _leader_field(record, "source_bar_age", _leader_field(record, "bar_age_seconds")),
        )
    )
    return age is not None and 0.0 <= age <= MAX_OPERATOR_BAR_AGE_SECONDS


def _leader_supporting_flow(record: dict) -> tuple[bool, float, float, float]:
    participation = _leader_number(
        _leader_field(
            record,
            "participation_score",
            _leader_field(record, "participation_surge_score", 0.0),
        )
    ) or 0.0
    volume_acceleration = _leader_number(
        _leader_field(record, "volume_acceleration", 0.0)
    ) or 0.0
    dollar_flow = _leader_number(
        _leader_field(
            record,
            "dollar_flow_acceleration_1m",
            _leader_field(record, "dollar_flow_acceleration", 0.0),
        )
    ) or 0.0
    active = bool(
        participation >= MIN_LEADER_PARTICIPATION
        and (
            volume_acceleration >= MIN_LEADER_VOLUME_ACCELERATION
            or dollar_flow >= MIN_LEADER_DOLLAR_FLOW_ACCELERATION
        )
    )
    return active, participation, volume_acceleration, dollar_flow


def _leader_marker(record: dict) -> str:
    stamp = str(
        _leader_field(
            record,
            "source_bar_timestamp",
            _leader_field(record, "last_bar_timestamp", _leader_field(record, "bar_timestamp", "")),
        )
        or ""
    )
    price = _leader_number(_leader_field(record, "price"))
    return f"{stamp}|{price if price is not None else ''}"


def _remember_leader_extension(record: dict, now: float) -> LeaderMemory | None:
    symbol = str(
        record.get("symbol") or _leader_decision(record).get("symbol") or ""
    ).strip().upper()
    if not symbol:
        return None

    current = _leader_memory.get(symbol)
    distance = _leader_number(_leader_field(record, "vwap_distance_pct"))
    if (
        distance is not None
        and distance >= PROVEN_LEADER_EXTENSION_PCT
        and _current_webull_mover(record)
        and _leader_fresh_source(record)
    ):
        pct_change = _leader_number(_leader_field(record, "pct_change"))
        price = _leader_number(_leader_field(record, "price"))
        if current is None:
            current = LeaderMemory(
                extended_at=now,
                last_seen_at=now,
                max_vwap_distance_pct=distance,
                peak_pct_change=pct_change,
                extension_price=price,
            )
        else:
            current.extended_at = now
            current.last_seen_at = now
            current.max_vwap_distance_pct = max(current.max_vwap_distance_pct, distance)
            if pct_change is not None:
                current.peak_pct_change = max(current.peak_pct_change or pct_change, pct_change)
            current.extension_price = price or current.extension_price
        _leader_memory[symbol] = current
    elif current is not None:
        current.last_seen_at = now
    return current


def leader_reset_evidence(
    record: dict,
    memory: LeaderMemory | None,
    *,
    now: float,
) -> dict:
    """Return bounded proven-leader reset/re-ignition evidence."""
    distance = _leader_number(_leader_field(record, "vwap_distance_pct"))
    thirty = _leader_tf(record, "30s")
    one = _leader_tf(record, "1m")
    three = _leader_tf(record, "3m")
    flow, participation, volume_acceleration, dollar_flow = _leader_supporting_flow(record)
    memory_age = (now - memory.extended_at) if memory is not None else None
    memory_fresh = bool(
        memory is not None
        and memory_age is not None
        and 0.0 <= memory_age <= LEADER_MEMORY_TTL_SECONDS
    )
    near_vwap = bool(distance is not None and abs(distance) <= NEAR_VWAP_WINDOW_PCT)
    current_mover = _current_webull_mover(record)
    fresh_source = _leader_fresh_source(record)

    reset_watch = bool(
        memory_fresh
        and near_vwap
        and thirty.get("bullish")
        and thirty.get("above_vwap")
        and one.get("bullish")
        and flow
        and current_mover
        and fresh_source
    )
    reclaimed = bool(
        distance is not None and 0.0 <= distance <= MAX_REIGNITION_VWAP_DISTANCE_PCT
    )
    reignition = bool(reset_watch and reclaimed and one.get("above_vwap"))
    three_confirmed = bool(
        reignition and three.get("bullish") and three.get("above_vwap")
    )
    stage = (
        THREE_MINUTE_CONFIRMATION
        if three_confirmed
        else REIGNITION
        if reignition
        else RESET_WATCH
        if reset_watch
        else "NONE"
    )

    marker = _leader_marker(record)
    stage_fresh = False
    if memory is not None:
        if stage == "NONE":
            memory.stage = "NONE"
            memory.transition_marker = None
        elif stage != memory.stage:
            memory.stage = stage
            memory.transition_marker = marker
            stage_fresh = True
        elif memory.transition_marker == marker:
            stage_fresh = True

    return {
        "active": stage != "NONE",
        "stage": stage,
        "stage_fresh": stage_fresh,
        "authority": LEADER_RESET_AUTHORITY,
        "entry_authority_changed": False,
        "alert_authority_changed": False,
        "memory_age_seconds": round(memory_age, 1) if memory_age is not None else None,
        "memory_ttl_seconds": LEADER_MEMORY_TTL_SECONDS,
        "prior_max_vwap_distance_pct": (
            round(memory.max_vwap_distance_pct, 3) if memory is not None else None
        ),
        "prior_peak_pct_change": memory.peak_pct_change if memory is not None else None,
        "current_vwap_distance_pct": distance,
        "near_vwap": near_vwap,
        "vwap_reclaimed": reclaimed,
        "thirty_second_bullish": bool(thirty.get("bullish")),
        "thirty_second_above_vwap": bool(thirty.get("above_vwap")),
        "one_minute_bullish": bool(one.get("bullish")),
        "one_minute_above_vwap": bool(one.get("above_vwap")),
        "three_minute_bullish": bool(three.get("bullish")),
        "three_minute_above_vwap": bool(three.get("above_vwap")),
        "participation_score": round(participation, 1),
        "volume_acceleration": round(volume_acceleration, 2),
        "dollar_flow_acceleration": round(dollar_flow, 2),
        "supporting_flow": flow,
        "current_webull_mover": current_mover,
        "fresh_source": fresh_source,
    }


def apply_leader_reset_marks(
    records: list[dict],
    *,
    now: float | None = None,
) -> list[dict]:
    """Attach bounded leader-reset evidence without mutating scanner records."""
    now = monotonic() if now is None else now
    output: list[dict] = []

    for record in records or []:
        memory = _remember_leader_extension(record, now)
        evidence = leader_reset_evidence(record, memory, now=now)
        if evidence.get("active"):
            row = deepcopy(record)
            row["leader_reset_reignition"] = evidence
            output.append(row)
        else:
            output.append(record)

    stale = [
        symbol
        for symbol, memory in _leader_memory.items()
        if now - memory.extended_at > LEADER_MEMORY_TTL_SECONDS
    ]
    for symbol in stale:
        _leader_memory.pop(symbol, None)
    return output


def reset_leader_memory() -> None:
    _leader_memory.clear()


# ---------------------------------------------------------------------------
# GS503 catalyst/company relative-scale market evidence
# ---------------------------------------------------------------------------

CATALYST_SCALE_AUTHORITY = "CATALYST_RELATIVE_SCALE_CONTEXT_ONLY"
_CATALYST_SCALE_SNAPSHOT_OWNER = "_walter_gs503_scale_snapshot_owner"
_CATALYST_SCALE_PREFILTER_OWNER = "_walter_gs503_scale_prefilter_owner"
_CATALYST_SCALE_ANALYZE_OWNER = "_walter_gs503_scale_analyze_owner"


def _scale_number(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if result > 0 else None


def _scale_money(value: float | None) -> str | None:
    if value is None:
        return None
    if value >= 1_000_000_000_000:
        return f"${value / 1_000_000_000_000:.2g}T"
    if value >= 1_000_000_000:
        return f"${value / 1_000_000_000:.2g}B"
    if value >= 1_000_000:
        return f"${value / 1_000_000:.3g}M"
    if value >= 1_000:
        return f"${value / 1_000:.3g}K"
    return f"${value:,.0f}"


def _scale_ratio_text(value: float | None) -> str | None:
    if value is None:
        return None
    if value >= 10:
        return f"{value:.0f}x"
    if value >= 1:
        return f"{value:.1f}x"
    return f"{value * 100:.0f}%"


def _relative_scale_band(
    ratio: float | None,
    *,
    market_cap_available: bool,
    event_amount_available: bool,
) -> str:
    if ratio is None:
        if not market_cap_available:
            return "NOT_EVALUATED_NO_MARKET_CAP"
        if not event_amount_available:
            return "NOT_EVALUATED_NO_EVENT_AMOUNT"
        return "NOT_EVALUATED_NO_COMPARABLE_RATIO"
    if ratio >= 1.0:
        return "COMPANY_SCALE_OR_LARGER"
    if ratio >= 0.25:
        return "MAJOR_RELATIVE_SCALE"
    if ratio >= 0.05:
        return "MATERIAL_RELATIVE_SCALE"
    return "LIMITED_RELATIVE_SCALE"


def _scale_quantity_values(story: dict, role: str) -> list[float]:
    values: list[float] = []
    for item in story.get("quantities") or []:
        if str(item.get("role") or "") != role:
            continue
        value = _scale_number(item.get("normalized_value"))
        if value is not None:
            values.append(value)
    return values


def market_cap_reference(
    record: dict,
    candidate: dict | None = None,
) -> tuple[float | None, str | None]:
    """Resolve already-observed market-cap evidence without any provider request."""
    for source in (record, candidate or {}):
        for key in ("market_cap_reference", "market_cap", "market_value"):
            value = _scale_number(source.get(key))
            if value is not None:
                label = (
                    source.get("market_cap_source")
                    or source.get("market_value_source")
                    or (
                        "Webull native radar market_value"
                        if key == "market_cap_reference"
                        else key
                    )
                )
                return value, str(label)
    return None, None


def company_scale_context(record: dict, candidate: dict | None = None) -> dict:
    """Return factual catalyst/company relative-scale context without trade authority."""
    story = deepcopy(record.get("catalyst_story") or {})
    magnitude = deepcopy(record.get("catalyst_magnitude") or {})

    if not magnitude and record.get("headline"):
        from mide.gs479_headline_catalyst_magnitude import headline_magnitude_context

        magnitude = headline_magnitude_context(str(record.get("headline") or ""))

    market_cap, market_cap_source = market_cap_reference(record, candidate)

    deal_values = _scale_quantity_values(story, "DEAL_OR_BACKLOG")
    revenue_values = _scale_quantity_values(story, "REVENUE")
    investment_values = _scale_quantity_values(story, "INVESTMENT_OR_FUNDING")
    dilution_values = _scale_quantity_values(story, "DILUTION_OR_FINANCING")
    headline_amount = _scale_number(magnitude.get("largest_stated_dollar_amount"))

    risk_categories = list(story.get("risk_categories") or [])
    positive_categories = list(story.get("positive_attention_categories") or [])
    risk_event = bool(risk_categories)
    merger_or_acquisition = "M_AND_A_INVESTMENT" in positive_categories

    amount = None
    amount_role = None
    if risk_event and dilution_values:
        amount, amount_role = max(dilution_values), "DILUTION_OR_FINANCING"
    elif deal_values:
        amount, amount_role = max(deal_values), "DEAL_OR_BACKLOG"
    elif investment_values:
        amount, amount_role = max(investment_values), "INVESTMENT_OR_FUNDING"
    elif revenue_values and not merger_or_acquisition:
        amount, amount_role = max(revenue_values), "REVENUE"
    elif headline_amount is not None and (
        bool(magnitude.get("contractual_language")) or positive_categories
    ):
        amount, amount_role = headline_amount, "HEADLINE_STATED_AMOUNT"

    duration = _scale_number(magnitude.get("stated_duration_years"))
    total_ratio = (
        amount / market_cap
        if amount is not None and market_cap is not None
        else None
    )

    annualized_amount = None
    annualized_ratio = None
    if (
        amount is not None
        and duration is not None
        and duration >= 1
        and amount_role in {"DEAL_OR_BACKLOG", "HEADLINE_STATED_AMOUNT"}
        and bool(magnitude.get("contractual_language"))
    ):
        annualized_amount = amount / duration
        if market_cap is not None:
            annualized_ratio = annualized_amount / market_cap

    comparison_ratio = (
        annualized_ratio if annualized_ratio is not None else total_ratio
    )
    band = _relative_scale_band(
        comparison_ratio,
        market_cap_available=market_cap is not None,
        event_amount_available=amount is not None,
    )

    if risk_event or amount_role == "DILUTION_OR_FINANCING":
        event_direction = "RISK_CONTEXT"
    elif positive_categories or amount_role:
        event_direction = "POSITIVE_ATTENTION_CONTEXT"
    else:
        event_direction = "UNCLASSIFIED_CONTEXT"

    summary_parts: list[str] = []
    if market_cap is not None and amount is None and merger_or_acquisition:
        summary_parts.append(
            f"Company scale: current market cap {_scale_money(market_cap)} · "
            "transaction consideration not stated in Walter's selected source"
        )
    if amount is not None and market_cap is not None:
        prefix = (
            "Risk scale"
            if event_direction == "RISK_CONTEXT"
            else "Company scale"
        )
        summary_parts.append(
            f"{prefix}: {_scale_money(amount)} stated = "
            f"{_scale_ratio_text(total_ratio)} current "
            f"{_scale_money(market_cap)} market cap"
        )
        if annualized_amount is not None and annualized_ratio is not None:
            summary_parts.append(
                f"~{_scale_money(annualized_amount)}/yr = "
                f"{_scale_ratio_text(annualized_ratio)} market cap over {duration:g}y"
            )

    return {
        "authority": CATALYST_SCALE_AUTHORITY,
        "market_cap_reference": market_cap,
        "market_cap_source": market_cap_source,
        "market_cap_available": market_cap is not None,
        "event_amount": amount,
        "event_amount_role": amount_role,
        "stated_duration_years": duration,
        "total_value_to_market_cap_ratio": (
            round(total_ratio, 4) if total_ratio is not None else None
        ),
        "annualized_contract_value": annualized_amount,
        "annualized_value_to_market_cap_ratio": (
            round(annualized_ratio, 4) if annualized_ratio is not None else None
        ),
        "comparison_ratio_used": (
            round(comparison_ratio, 4) if comparison_ratio is not None else None
        ),
        "relative_scale_band": band,
        "event_direction": event_direction,
        "summary": " · ".join(summary_parts),
        "band_contract": {
            "limited_relative_scale": "<5% of market cap",
            "material_relative_scale": "5%-<25% of market cap",
            "major_relative_scale": "25%-<100% of market cap",
            "company_scale_or_larger": ">=100% of market cap",
            "multi_year_contract_basis": (
                "straight-line annualized stated value when duration is disclosed"
            ),
        },
        "revenue_recognition_inferred": False,
        "profitability_inferred": False,
        "valuation_impact_inferred": False,
        "closing_probability_inferred": False,
        "price_target_inferred": False,
        "trading_authority_changed": False,
    }


def _scale_inherit(wrapper, wrapped) -> None:
    for name, value in getattr(wrapped, "__dict__", {}).items():
        if name.startswith("_gs") and not hasattr(wrapper, name):
            setattr(wrapper, name, value)


def install_catalyst_scale_snapshot_reference() -> None:
    """Carry already-fetched Webull native market value into snapshot evidence."""
    from mide.webull_live import LiveWebullProvider

    current = LiveWebullProvider.snapshots
    if getattr(current, _CATALYST_SCALE_SNAPSHOT_OWNER, False):
        return

    @wraps(current)
    def snapshots_with_market_cap(self, symbols):
        snapshots = current(self, symbols)
        native = getattr(self, "_native_radar_prices", {}) or {}
        output = {}
        for symbol, snapshot in (snapshots or {}).items():
            row = dict(snapshot)
            radar = native.get(str(symbol).strip().upper()) or {}
            market_cap = _scale_number(
                radar.get("market_value") or radar.get("market_cap")
            )
            if market_cap is not None:
                row["market_cap_reference"] = market_cap
                row["market_cap_source"] = "Webull native radar market_value"
            output[symbol] = row
        return output

    _scale_inherit(snapshots_with_market_cap, current)
    setattr(
        snapshots_with_market_cap,
        _CATALYST_SCALE_SNAPSHOT_OWNER,
        True,
    )
    snapshots_with_market_cap._gs503_catalyst_company_scale = True
    snapshots_with_market_cap._gs503_original = current
    LiveWebullProvider.snapshots = snapshots_with_market_cap


def install_catalyst_scale_prefilter_reference() -> None:
    """Carry market-cap evidence through prefilter without changing membership."""
    from mide import discovery

    current = discovery.prefilter_snapshots
    if getattr(current, _CATALYST_SCALE_PREFILTER_OWNER, False):
        return

    @wraps(current)
    def prefilter_with_market_cap(snapshots, settings):
        selected = current(snapshots, settings)
        output = []
        for candidate in selected or []:
            row = dict(candidate)
            source = (
                (snapshots or {}).get(
                    str(row.get("symbol") or "").upper()
                )
                or {}
            )
            market_cap = _scale_number(
                source.get("market_cap_reference")
                or source.get("market_cap")
                or source.get("market_value")
            )
            if market_cap is not None:
                row["market_cap_reference"] = market_cap
                row["market_cap_source"] = str(
                    source.get("market_cap_source")
                    or "Webull native radar market_value"
                )
            output.append(row)
        return output

    _scale_inherit(prefilter_with_market_cap, current)
    setattr(
        prefilter_with_market_cap,
        _CATALYST_SCALE_PREFILTER_OWNER,
        True,
    )
    prefilter_with_market_cap._gs503_catalyst_company_scale = True
    prefilter_with_market_cap._gs503_original = current
    discovery.prefilter_snapshots = prefilter_with_market_cap


def install_catalyst_scale_analyzed_context() -> None:
    """Attach relative-scale evidence after analysis without changing scores/rank."""
    from mide import discovery

    current = discovery.analyze_candidates
    if getattr(current, _CATALYST_SCALE_ANALYZE_OWNER, False):
        return

    @wraps(current)
    def analyze_with_company_scale(
        client,
        candidates,
        news_index,
        discovery_reasons,
    ):
        records = current(
            client,
            candidates,
            news_index,
            discovery_reasons,
        )
        by_symbol = {
            str(item.get("symbol") or "").strip().upper(): item
            for item in candidates or []
        }
        output = []
        for record in records or []:
            symbol = str(record.get("symbol") or "").strip().upper()
            candidate = by_symbol.get(symbol) or {}
            row = dict(record)
            market_cap, source = market_cap_reference(row, candidate)
            if market_cap is not None:
                row["market_cap_reference"] = market_cap
                row["market_cap_source"] = source
            row["catalyst_company_scale"] = company_scale_context(
                row,
                candidate,
            )
            output.append(row)

        diagnostics = getattr(client, "diagnostics", None)
        if isinstance(diagnostics, dict):
            contexts = [
                item.get("catalyst_company_scale") or {}
                for item in output
            ]
            diagnostics["gs503_catalyst_company_scale"] = {
                "authority": CATALYST_SCALE_AUTHORITY,
                "records_evaluated": len(output),
                "records_with_market_cap": sum(
                    bool(item.get("market_cap_available"))
                    for item in contexts
                ),
                "records_with_economic_amount": sum(
                    bool(item.get("event_amount"))
                    for item in contexts
                ),
                "company_scale_or_larger": sum(
                    item.get("relative_scale_band")
                    == "COMPANY_SCALE_OR_LARGER"
                    for item in contexts
                ),
                "additional_provider_requests": 0,
                "ranking_changed": False,
                "trading_authority_changed": False,
            }
        return output

    _scale_inherit(analyze_with_company_scale, current)
    setattr(
        analyze_with_company_scale,
        _CATALYST_SCALE_ANALYZE_OWNER,
        True,
    )
    analyze_with_company_scale._gs503_catalyst_company_scale = True
    analyze_with_company_scale._gs503_original = current
    discovery.analyze_candidates = analyze_with_company_scale


def install_catalyst_company_scale_evidence() -> None:
    """Install all GS503 Market Evidence responsibilities in historical order."""
    install_catalyst_scale_snapshot_reference()
    install_catalyst_scale_prefilter_reference()
    install_catalyst_scale_analyzed_context()


# ---------------------------------------------------------------------------
# GS459 price-trajectory market evidence
# ---------------------------------------------------------------------------

PRICE_TRAJECTORY_DISCOVERY_OWNER = "_walter_gs459_price_trajectory_metrics_owner"


def _price_trajectory_number(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _price_trajectory_return_pct(start: float, end: float) -> float:
    if start == 0:
        return 0.0
    return (end / start - 1.0) * 100.0


def price_trajectory_metrics(frame) -> dict:
    """Describe sparkline-like path acceleration from existing 1-minute bars."""
    defaults = {
        "price_trajectory_available": False,
        "price_change_3m_pct": 0.0,
        "price_change_5m_path_pct": 0.0,
        "price_change_prior_7m_pct": 0.0,
        "price_velocity_3m_pct_per_min": 0.0,
        "price_velocity_prior_7m_pct_per_min": 0.0,
        "price_path_acceleration_pct_per_min": 0.0,
        "positive_close_ratio_5m": 0.0,
        "giveback_from_5m_high_pct": 0.0,
    }
    try:
        if frame is None or len(frame) < 11:
            return defaults
        closes = frame["close"].astype(float).tail(11)
        highs = frame["high"].astype(float).tail(5)
    except Exception:
        return defaults
    if len(closes) < 11 or len(highs) < 1:
        return defaults

    current = float(closes.iloc[-1])
    three_start = float(closes.iloc[-4])
    five_start = float(closes.iloc[-6])
    prior_start = float(closes.iloc[-11])
    prior_end = float(closes.iloc[-4])

    change_3m = _price_trajectory_return_pct(three_start, current)
    change_5m = _price_trajectory_return_pct(five_start, current)
    prior_7m_change = _price_trajectory_return_pct(prior_start, prior_end)
    recent_velocity = change_3m / 3.0
    prior_velocity = prior_7m_change / 7.0
    acceleration = recent_velocity - prior_velocity

    recent_closes = closes.tail(6)
    changes = recent_closes.diff().dropna()
    positive_ratio = (
        float((changes > 0).mean()) if len(changes) else 0.0
    )
    recent_high = float(highs.max())
    giveback = (
        max(0.0, (recent_high - current) / recent_high * 100.0)
        if recent_high > 0
        else 0.0
    )

    return {
        "price_trajectory_available": True,
        "price_change_3m_pct": round(change_3m, 3),
        "price_change_5m_path_pct": round(change_5m, 3),
        "price_change_prior_7m_pct": round(prior_7m_change, 3),
        "price_velocity_3m_pct_per_min": round(recent_velocity, 4),
        "price_velocity_prior_7m_pct_per_min": round(prior_velocity, 4),
        "price_path_acceleration_pct_per_min": round(acceleration, 4),
        "positive_close_ratio_5m": round(positive_ratio, 3),
        "giveback_from_5m_high_pct": round(giveback, 3),
    }


def install_price_trajectory_metrics() -> None:
    """Attach GS459 path evidence to the existing participation metric boundary."""
    from mide import discovery

    current = discovery.intraday_participation_metrics
    if getattr(current, PRICE_TRAJECTORY_DISCOVERY_OWNER, False):
        return

    def intraday_participation_metrics(frame):
        from mide import gs459_price_trajectory_attention as gs459

        result = dict(current(frame) or {})
        result.update(gs459.price_trajectory_metrics(frame))
        return result

    for name, value in getattr(current, "__dict__", {}).items():
        if name.startswith("_gs") and not hasattr(
            intraday_participation_metrics,
            name,
        ):
            setattr(intraday_participation_metrics, name, value)
    intraday_participation_metrics._gs459_price_trajectory_metrics = True
    intraday_participation_metrics._gs459_original = current
    setattr(
        intraday_participation_metrics,
        PRICE_TRAJECTORY_DISCOVERY_OWNER,
        True,
    )
    discovery.intraday_participation_metrics = intraday_participation_metrics


# ---------------------------------------------------------------------------
# GS404 reset/retest attention evidence
# ---------------------------------------------------------------------------
#
# Market Evidence owns the provider-free facts that identify a fresh near-VWAP reset
# after prior extension. LOOK NOW state meaning and visible awareness injection remain
# outside this component.


def reset_retest_number(
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


def reset_retest_one_minute(record: dict) -> dict:
    states = record.get("timeframes") or {}
    value = (
        states.get("1m")
        if isinstance(states, dict)
        else None
    )
    return (
        dict(value)
        if isinstance(value, dict)
        else {}
    )


def reset_retest_current_webull_radar_attention(
    record: dict,
) -> bool:
    from mide import gs404_reset_retest_look_now as gs404

    reasons = " | ".join(
        str(value or "")
        for value in (
            record.get("discovery_reasons")
            or []
        )
    )
    return bool(
        gs404.WEBULL_DAY_GAINER_REASON in reasons
        or gs404.WEBULL_FIVE_MINUTE_REASON in reasons
    )


def reset_retest_fresh_source(record: dict) -> bool:
    from mide.gs373_operator_visibility_freshness import (
        MAX_OPERATOR_BAR_AGE_SECONDS,
    )

    age = reset_retest_number(
        record,
        "source_bar_age_seconds",
        "source_bar_age",
        "bar_age_seconds",
    )
    return bool(
        age is not None
        and 0.0 <= age <= MAX_OPERATOR_BAR_AGE_SECONDS
    )


def reset_retest_attention_evidence(record: dict) -> dict:
    """Return provider-free GS404 reset/retest attention evidence."""
    from mide import gs404_reset_retest_look_now as gs404

    previous = (
        record.get("opportunity_pulse_previous")
        or {}
    )
    continuity = bool(previous)

    previous_distance = reset_retest_number(
        previous,
        "vwap_distance_pct",
    )
    current_distance = reset_retest_number(
        record,
        "vwap_distance_pct",
    )
    previous_extended = bool(
        previous_distance is not None
        and previous_distance
        > gs404.PREVIOUS_EXTENSION_MIN_PCT
    )
    near_vwap_now = bool(
        current_distance is not None
        and abs(current_distance)
        <= gs404.NEAR_VWAP_WINDOW_PCT
    )

    one = reset_retest_one_minute(record)
    one_minute_bullish = bool(
        one.get("supertrend")
    )

    participation = (
        reset_retest_number(
            record,
            "participation_score",
            "participation_surge_score",
            default=0.0,
        )
        or 0.0
    )
    volume_acceleration = (
        reset_retest_number(
            record,
            "volume_acceleration",
            default=0.0,
        )
        or 0.0
    )
    dollar_flow = (
        reset_retest_number(
            record,
            "dollar_flow_acceleration_1m",
            "dollar_flow_acceleration",
            default=0.0,
        )
        or 0.0
    )

    participation_present = bool(
        participation
        >= gs404.MIN_PARTICIPATION
    )
    flow_present = bool(
        volume_acceleration
        >= gs404.MIN_VOLUME_ACCELERATION
        or dollar_flow
        >= gs404.MIN_DOLLAR_FLOW_ACCELERATION
    )
    current_radar_attention = (
        reset_retest_current_webull_radar_attention(
            record
        )
    )
    fresh_source = reset_retest_fresh_source(
        record
    )

    recent = bool(
        continuity
        and previous_extended
        and near_vwap_now
        and one_minute_bullish
        and participation_present
        and flow_present
        and current_radar_attention
        and fresh_source
    )
    return {
        "recent": recent,
        "trigger": (
            "RESET_RETEST_NEAR_VWAP"
            if recent
            else None
        ),
        "chart_review_only": True,
        "entry_authority_unchanged": True,
        "continuity": continuity,
        "previous_vwap_distance_pct": previous_distance,
        "previous_extended": previous_extended,
        "current_vwap_distance_pct": current_distance,
        "near_vwap_now": near_vwap_now,
        "one_minute_supertrend_bullish": one_minute_bullish,
        "participation_score": round(
            float(participation),
            1,
        ),
        "participation_present": participation_present,
        "volume_acceleration": round(
            float(volume_acceleration),
            2,
        ),
        "dollar_flow_acceleration": round(
            float(dollar_flow),
            2,
        ),
        "flow_present": flow_present,
        "current_webull_radar_attention": current_radar_attention,
        "fresh_source": fresh_source,
    }


def reset_retest_eligible(record: dict) -> bool:
    return bool(
        reset_retest_attention_evidence(
            record
        )["recent"]
    )


# ---------------------------------------------------------------------------
# GS456 canonical 30s VWAP / SuperTrend alignment evidence
# ---------------------------------------------------------------------------
#
# Market Evidence owns retention of the already-paid 30s VWAP/SuperTrend alignment
# facts. The historical GS456 module remains the startup/compatibility seam. This
# layer reuses GS378's installed primary-VWAP policy and SuperTrend pass; it adds no
# provider request and no entry/qualification authority.


def canonical_30s_empty_alignment() -> dict:
    from mide import gs456_canonical_30s_vwap_cross as gs456

    return {
        "above_vwap": False,
        "supertrend_bullish": False,
        "above_ema65": False,
        "higher_highs_higher_lows": None,
        "aligned": False,
        "vwap_value": None,
        "vwap_anchor_mode": "UNAVAILABLE",
        "vwap_anchor_time_et": None,
        "supertrend_value": None,
        "st_vwap_line_cross": {
            "timeframe": "30s",
            "crossed": False,
            "recent": False,
            "new": False,
            "timestamp": None,
            "age_seconds": None,
            "current_confirmed": False,
        },
        "vwap_truth_authority": gs456.AUTHORITY,
        "source": gs456.SOURCE,
    }


def canonical_30s_alignment_truth(frame_30s: pd.DataFrame | None) -> dict:
    """Retain canonical 30s VWAP/ST truth from GS378's already-paid calculation."""
    from mide import gs378_live_vwap_st_crossover as gs378
    from mide import gs456_canonical_30s_vwap_cross as gs456

    day = gs378._eastern_day(frame_30s)
    if day.empty:
        return canonical_30s_empty_alignment()

    context = gs378.primary_vwap_context(day)
    day = context.get("day")
    primary = context.get("series")
    if day is None or day.empty or primary is None or primary.empty:
        return canonical_30s_empty_alignment()

    vwap = primary.reindex(day.index)
    close = day["close"].astype(float)
    latest_close = (
        maturation_finite(close.iloc[-1])
        if len(close)
        else None
    )
    latest_vwap = (
        maturation_finite(vwap.iloc[-1])
        if len(vwap)
        else None
    )

    ema65 = (
        gs378.ema(close, 65).iloc[-1]
        if len(day) >= 65
        else float("nan")
    )
    st_line, direction = gs378.supertrend(
        day,
        10,
        3,
    )
    latest_st = (
        maturation_finite(st_line.iloc[-1])
        if len(st_line)
        else None
    )
    hh = gs378._higher_highs(day)
    hl = (
        gs378.higher_lows(day)
        if len(day) >= 4
        else None
    )
    structure = (
        None
        if hh is None or hl is None
        else bool(hh and hl)
    )

    above_vwap = bool(
        latest_close is not None
        and latest_vwap is not None
        and latest_close >= latest_vwap
    )
    bullish = bool(
        len(direction)
        and direction.iloc[-1]
    )
    above_ema = bool(
        pd.notna(ema65)
        and latest_close is not None
        and latest_close >= float(ema65)
    )
    aligned = bool(
        above_vwap
        and bullish
        and above_ema
        and structure is not False
    )

    cross = maturation_line_cross_event(
        day,
        vwap,
        st_line,
        direction,
        "30s",
        latest_source_time=day.index[-1],
    )

    anchor_time = context.get("anchor_time")
    return {
        "above_vwap": above_vwap,
        "supertrend_bullish": bullish,
        "above_ema65": above_ema,
        "higher_highs_higher_lows": structure,
        "aligned": aligned,
        "vwap_value": (
            round(latest_vwap, 6)
            if latest_vwap is not None
            else None
        ),
        "vwap_anchor_mode": context.get("anchor_mode"),
        "vwap_anchor_time_et": (
            anchor_time.isoformat()
            if anchor_time is not None
            else None
        ),
        "supertrend_value": (
            round(latest_st, 6)
            if latest_st is not None
            else None
        ),
        "st_vwap_line_cross": cross,
        "vwap_truth_authority": gs456.AUTHORITY,
        "source": gs456.SOURCE,
    }


def canonical_alignment_summary_with_30s_truth(
    day_1m: pd.DataFrame,
    primary_1m: pd.Series,
    frame_30s: pd.DataFrame | None = None,
) -> dict:
    """Preserve GS378's 1m/3m contract while retaining canonical 30s values."""
    from mide import gs378_live_vwap_st_crossover as gs378

    details: dict[str, dict] = {
        "30s": canonical_30s_alignment_truth(
            frame_30s
        ),
        "1m": gs378._alignment_evaluation(
            day_1m,
            primary_1m,
            "1m",
        ),
    }
    frame_3m = gs378._timeframe_frame(
        day_1m,
        "3m",
    )
    details["3m"] = (
        gs378._alignment_evaluation(
            frame_3m,
            primary_1m,
            "3m",
        )
    )
    score = sum(
        bool(
            details[label].get("aligned")
        )
        for label in (
            "30s",
            "1m",
            "3m",
        )
    )
    return {
        "timeframe_alignment": details,
        "alignment_score": score,
        "alignment_total": 3,
        "alignment_label": (
            gs378._ALIGNMENT_LABELS[score]
        ),
    }


def install_canonical_30s_alignment_truth() -> None:
    """Bind GS456 alignment evidence at the historical GS378 install point."""
    from mide import gs378_live_vwap_st_crossover as gs378

    current = gs378._alignment_summary
    if getattr(
        current,
        "_gs456_canonical_30s_vwap",
        False,
    ):
        return

    canonical_alignment_summary_with_30s_truth._gs456_canonical_30s_vwap = True
    canonical_alignment_summary_with_30s_truth._gs456_original = current
    gs378._alignment_summary = (
        canonical_alignment_summary_with_30s_truth
    )


# ---------------------------------------------------------------------------
# GS456 canonical 30s VWAP truth propagation into GS397
# ---------------------------------------------------------------------------
#
# Market Evidence owns how canonical 30s VWAP/ST facts are carried through GS397's
# retained record. The historical GS456 installer remains the compatibility seam.


def canonical_30s_primary_above_vwap(
    original,
    record: dict,
    alignment_30s: dict,
    tripwire: dict,
) -> bool | None:
    """Prefer canonical 30s close/VWAP truth before GS397's older fallback."""
    from mide import gs456_canonical_30s_vwap_cross as gs456

    close = maturation_finite(
        tripwire.get("latest_close")
    )
    vwap = maturation_finite(
        alignment_30s.get("vwap_value")
    )
    if close is not None and vwap is not None:
        return close >= vwap
    if (
        alignment_30s.get("above_vwap") is not None
        and alignment_30s.get("vwap_truth_authority")
        == gs456.AUTHORITY
    ):
        return bool(
            alignment_30s.get("above_vwap")
        )
    return original(
        record,
        alignment_30s,
        tripwire,
    )


def canonicalize_gs397_with_30s_vwap(
    original,
    record: dict,
) -> dict:
    """Carry canonical 30s VWAP/ST/cross facts without changing entry authority."""
    from mide import gs456_canonical_30s_vwap_cross as gs456

    updated = original(record)
    alignment = deepcopy(
        updated.get("timeframe_alignment")
        or {}
    )
    thirty = dict(
        alignment.get("30s")
        or {}
    )
    if (
        thirty.get("vwap_truth_authority")
        != gs456.AUTHORITY
    ):
        return updated

    cross = deepcopy(
        thirty.get("st_vwap_line_cross")
        or {}
    )
    updated["vwap_30s_value"] = (
        thirty.get("vwap_value")
    )
    updated["vwap_30s_anchor_mode"] = (
        thirty.get("vwap_anchor_mode")
    )
    updated["vwap_30s_anchor_time_et"] = (
        thirty.get("vwap_anchor_time_et")
    )
    updated["st_vwap_30s_line_cross"] = cross

    timeframes = deepcopy(
        updated.get("timeframes")
        or {}
    )
    tf30 = dict(
        timeframes.get("30s")
        or {}
    )
    tf30.update(
        {
            "vwap_value": thirty.get(
                "vwap_value"
            ),
            "vwap_anchor_mode": thirty.get(
                "vwap_anchor_mode"
            ),
            "vwap_anchor_time_et": thirty.get(
                "vwap_anchor_time_et"
            ),
            "supertrend_value": thirty.get(
                "supertrend_value"
            ),
            "st_vwap_line_cross": cross,
            "vwap_truth_authority": (
                gs456.AUTHORITY
            ),
        }
    )
    timeframes["30s"] = tf30
    updated["timeframes"] = timeframes
    return updated


def install_canonical_30s_gs397_propagation() -> None:
    """Bind GS456 canonical 30s propagation at GS397's historical seams."""
    from mide import gs397_canonical_30s_tripwire_truth as gs397

    current_above = gs397._primary_above_vwap
    if not getattr(
        current_above,
        "_gs456_canonical_30s_vwap",
        False,
    ):
        @wraps(current_above)
        def primary_above_vwap(
            record: dict,
            alignment_30s: dict,
            tripwire: dict,
        ):
            return canonical_30s_primary_above_vwap(
                current_above,
                record,
                alignment_30s,
                tripwire,
            )

        primary_above_vwap._gs456_canonical_30s_vwap = True
        primary_above_vwap._gs456_original = (
            current_above
        )
        gs397._primary_above_vwap = (
            primary_above_vwap
        )

    current_canonicalize = (
        gs397.canonicalize_record
    )
    if getattr(
        current_canonicalize,
        "_gs456_canonical_30s_vwap",
        False,
    ):
        return

    @wraps(current_canonicalize)
    def canonicalize_record(
        record: dict,
    ) -> dict:
        return canonicalize_gs397_with_30s_vwap(
            current_canonicalize,
            record,
        )

    canonicalize_record._gs456_canonical_30s_vwap = True
    canonicalize_record._gs456_original = (
        current_canonicalize
    )
    gs397.canonicalize_record = canonicalize_record


# ---------------------------------------------------------------------------
# GS456 canonical literal 30s cross preference for GS455 first rung
# ---------------------------------------------------------------------------
#
# Market Evidence owns whether retained literal 30s ST/VWAP cross truth supersedes
# the older bullish-flip tripwire for the first GS455 maturation rung. The historical
# GS456 installer remains the mutable compatibility seam.


def canonical_30s_progression_rung(
    original,
    record: dict,
) -> dict:
    """Prefer literal canonical 30s ST/VWAP cross evidence when confirmed."""
    event = dict(
        record.get("st_vwap_30s_line_cross")
        or {}
    )
    if not event:
        alignment = (
            record.get("timeframe_alignment")
            or {}
        )
        event = dict(
            (
                alignment.get("30s")
                or {}
            ).get("st_vwap_line_cross")
            or {}
        )
    if (
        event.get("crossed")
        and event.get("current_confirmed")
    ):
        event["kind"] = (
            "literal_30s_st_vwap_line_cross"
        )
        return event

    fallback = dict(
        original(record)
    )
    fallback.setdefault(
        "kind",
        "canonical_30s_tripwire_flip_fallback",
    )
    return fallback


def install_canonical_30s_progression_rung() -> None:
    """Bind GS456 literal-cross preference at GS455's historical first-rung seam."""
    from mide import gs455_early_ignition_3m_confirmation as gs455

    current = gs455._thirty_second_rung
    if getattr(
        current,
        "_gs456_literal_30s_cross",
        False,
    ):
        return

    @wraps(current)
    def thirty_second_rung(
        record: dict,
    ) -> dict:
        return canonical_30s_progression_rung(
            current,
            record,
        )

    thirty_second_rung._gs456_literal_30s_cross = True
    thirty_second_rung._gs456_original = current
    gs455._thirty_second_rung = (
        thirty_second_rung
    )


# ---------------------------------------------------------------------------
# GS455 ordered ST/VWAP maturation progression evidence
# ---------------------------------------------------------------------------
#
# Market Evidence owns numeric/timestamp normalization, rung extraction,
# halt/current-attention/support-flow evidence, the current 30s -> 15m ordered progression,
# and the fresh-rung signal. The historical gs455 module remains the calibration/monkeypatch
# seam for ladder/freshness thresholds and mutable helper names consumed by GS456/GS457/GS460.
# No provider request, qualification, readiness, state promotion, audio, or order authority
# lives here.


def progression_number(
    record: dict,
    *keys: str,
    default: float | None = None,
) -> float | None:
    """Return the first finite numeric value from retained record evidence."""
    for key in keys:
        value = record.get(key)
        if value is None or value == "":
            continue
        try:
            number = float(value)
        except (TypeError, ValueError):
            continue
        if math.isfinite(number):
            return number
    return default


def progression_timestamp(value: Any) -> datetime | None:
    """Parse one retained ISO timestamp for ordered-rung comparison."""
    if value in (None, ""):
        return None
    try:
        return datetime.fromisoformat(
            str(value).replace("Z", "+00:00")
        )
    except (TypeError, ValueError):
        return None


def thirty_second_progression_rung(record: dict) -> dict:
    """Return the historical GS455 30s fallback rung from retained market evidence."""
    from mide import gs455_early_ignition_3m_confirmation as gs455

    tripwire = record.get("thirty_second_tripwire") or {}
    stamp = (
        record.get("supertrend_30s_last_flip_timestamp")
        or tripwire.get("last_flip_timestamp")
    )
    age = progression_number(
        record,
        "supertrend_30s_last_flip_age_seconds",
        "supertrend_30s_flip_age_seconds",
    )
    if age is None:
        age = progression_number(
            tripwire,
            "last_flip_age_seconds",
        )
    bullish = bool(
        record.get("supertrend_30s_bullish")
        or tripwire.get("supertrend_bullish")
    )
    active = bool(stamp and bullish)
    return {
        "timeframe": "30s",
        "crossed": active,
        "recent": bool(
            active
            and age is not None
            and age <= gs455._RECENT_WINDOWS_SECONDS["30s"]
        ),
        "new": bool(
            active
            and age is not None
            and age <= gs455._NEW_WINDOWS_SECONDS["30s"]
        ),
        "timestamp": stamp,
        "age_seconds": age,
        "current_confirmed": bullish,
        "kind": "canonical_30s_tripwire_flip",
    }


def progression_rung_event(
    record: dict,
    label: str,
) -> dict:
    """Assemble one GS455 maturation rung from already-retained evidence."""
    from mide import gs455_early_ignition_3m_confirmation as gs455

    if label == "30s":
        # Preserve GS456's installed literal-cross wrapper at the historical seam.
        return gs455._thirty_second_rung(record)

    if label in {"1m", "3m"}:
        canonical = dict(
            (record.get("st_vwap_cross_events") or {}).get(label)
            or {}
        )
        detail = dict(
            (record.get("timeframes") or {}).get(label)
            or {}
        )
        enriched = dict(
            detail.get("st_vwap_line_cross")
            or {}
        )
        event = canonical or enriched
        if canonical and enriched:
            event = dict(canonical)
            event["current_confirmed"] = enriched.get(
                "current_confirmed",
                bool(
                    detail.get("above_vwap")
                    and detail.get("supertrend")
                ),
            )
        elif event:
            event.setdefault(
                "current_confirmed",
                bool(
                    detail.get("above_vwap")
                    and detail.get("supertrend")
                ),
            )
        return event

    if label in {"5m", "10m"}:
        detail = dict(
            (record.get("timeframes") or {}).get(label)
            or {}
        )
        return dict(
            detail.get("st_vwap_line_cross")
            or {}
        )

    maturation = (
        record.get("multitimeframe_maturation")
        or {}
    )
    detail = dict(
        (maturation.get("timeframes") or {}).get("15m")
        or {}
    )
    return dict(
        detail.get("st_vwap_line_cross")
        or {}
    )


def progression_halted(record: dict) -> bool:
    """Return whether retained status evidence says the symbol is halted/suspended."""
    if any(
        record.get(key) is True
        for key in (
            "halted",
            "is_halted",
            "suspended",
            "is_suspended",
        )
    ):
        return True
    text = " ".join(
        str(record.get(key) or "")
        for key in (
            "halt_status",
            "trading_status",
            "market_status",
            "status_reason",
        )
    ).lower()
    return "halt" in text or "suspend" in text


def progression_current_attention(record: dict) -> bool:
    """Return whether retained discovery/news evidence supplies live attention support."""
    reasons = " ".join(
        str(item)
        for item in (
            record.get("discovery_reasons")
            or []
        )
    )
    if "webull native:" in reasons.lower():
        return True
    try:
        from mide.gs309_current_attention_mission import (
            current_attention_provenance,
        )

        if current_attention_provenance(record):
            return True
    except Exception:
        pass
    return bool(
        str(
            record.get("headline")
            or ""
        ).strip()
        or record.get("fresh_news")
        or record.get("news_catalyst")
        or record.get("has_catalyst")
        or record.get("catalyst_confirmed")
    )


def progression_supporting_flow(record: dict) -> bool:
    """Return the historical GS455 supporting-flow evidence gate."""
    from mide import gs455_early_ignition_3m_confirmation as gs455

    volume = (
        progression_number(
            record,
            "volume",
            default=0.0,
        )
        or 0.0
    )
    participation = (
        progression_number(
            record,
            "participation_surge_score",
            "participation_score",
            default=0.0,
        )
        or 0.0
    )
    expansion = (
        progression_number(
            record,
            "expansion_quality",
            "expansion_score",
            default=0.0,
        )
        or 0.0
    )
    volume_acceleration = (
        progression_number(
            record,
            "volume_acceleration",
            default=0.0,
        )
        or 0.0
    )
    dollar_flow = (
        progression_number(
            record,
            "dollar_flow_acceleration_5m",
            "dollar_flow_acceleration",
            default=0.0,
        )
        or 0.0
    )
    return bool(
        volume >= 100_000
        or participation >= 20.0
        or expansion >= 40.0
        or volume_acceleration >= 1.0
        or dollar_flow >= 1.25
        or gs455._current_attention(record)
    )


def crossover_progression(record: dict) -> dict:
    """Return Walter's ordered current 30s->15m maturation ladder."""
    from mide import gs455_early_ignition_3m_confirmation as gs455

    active_rungs: list[str] = []
    timestamps: list[datetime] = []
    fresh_rungs: list[str] = []
    rung_events: dict[str, dict] = {}

    for label in gs455.CROSSOVER_LADDER:
        event = gs455._rung_event(record, label)
        rung_events[label] = event
        if (
            not event.get("crossed")
            or not event.get("current_confirmed")
        ):
            continue
        active_rungs.append(label)
        stamp = progression_timestamp(
            event.get("timestamp")
        )
        if stamp is not None:
            timestamps.append(stamp)
        if event.get("new"):
            fresh_rungs.append(label)

    ordered = all(
        earlier <= later
        for earlier, later in zip(
            timestamps,
            timestamps[1:],
        )
    )
    highest = (
        active_rungs[-1]
        if active_rungs
        else None
    )
    latest_new = (
        fresh_rungs[-1]
        if fresh_rungs
        else None
    )

    if any(
        label in active_rungs
        for label in ("5m", "10m", "15m")
    ):
        stage = "PERSISTENCE"
    elif "3m" in active_rungs:
        stage = "CONFIRMATION"
    elif any(
        label in active_rungs
        for label in ("30s", "1m")
    ):
        stage = "IGNITION"
    else:
        stage = "NONE"

    return {
        "ladder": list(gs455.CROSSOVER_LADDER),
        "active_rungs": active_rungs,
        "fresh_rungs": fresh_rungs,
        "depth": len(active_rungs),
        "ordered": ordered,
        "highest_rung": highest,
        "latest_new_rung": latest_new,
        "stage": stage,
        "sequence": " -> ".join(active_rungs),
        "events": rung_events,
    }


def progression_signal(record: dict) -> dict:
    """Return a fresh operator signal from a newly reached ordered maturation rung."""
    from mide import gs455_early_ignition_3m_confirmation as gs455

    progression = gs455.crossover_progression(
        record
    )
    new_rung = progression.get(
        "latest_new_rung"
    )
    distance = progression_number(
        record,
        "vwap_distance_pct",
    )
    relation = str(
        record.get("vwap_relation") or ""
    ).strip().lower()
    above_vwap = bool(
        relation == "above"
        or (
            distance is not None
            and distance >= 0.0
        )
    )
    supported = gs455._supporting_flow(record)
    depth = int(
        progression.get("depth") or 0
    )
    ordered = bool(
        progression.get("ordered")
    )
    active = bool(
        new_rung
        and not gs455._halted(record)
        and above_vwap
        and supported
        and (ordered or depth <= 1)
    )
    event = dict(
        (
            progression.get("events")
            or {}
        ).get(new_rung)
        or {}
    )
    return {
        "active": active,
        "new_rung": new_rung,
        "timestamp": event.get("timestamp"),
        "stage": progression.get("stage"),
        "sequence": (
            progression.get("sequence")
            or ""
        ),
        "depth": depth,
        "ordered": ordered,
        "supporting_flow": supported,
        "vwap_distance_pct": distance,
    }


# ---------------------------------------------------------------------------
# GS455 literal ST/VWAP line-cross enrichment
# ---------------------------------------------------------------------------
#
# These helpers enrich already-paid GS378/GS421 SuperTrend passes with literal
# ST-line/VWAP-line cross metadata. They perform no provider/history request.
# Historical gs455 remains the calibration seam for freshness windows and wrapper
# identity so warm runtimes and regression monkeypatches keep the same behavior.


def maturation_finite(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if pd.notna(number) and number not in (float("inf"), float("-inf")) else None


def maturation_line_cross_event(
    frame,
    vwap,
    st_line,
    trend,
    label: str,
    *,
    latest_source_time,
) -> dict:
    """Retain a literal ST-line/VWAP-line cross from an already-paid ST pass."""
    from mide import gs455_early_ignition_3m_confirmation as gs455

    if frame is None or getattr(frame, "empty", True) or len(frame) < 2:
        return {
            "timeframe": label,
            "crossed": False,
            "recent": False,
            "new": False,
            "timestamp": None,
            "age_seconds": None,
            "current_confirmed": False,
        }

    close = frame["close"].astype(float)
    valid = st_line.notna() & vwap.notna()
    bullish = trend.fillna(False).astype(bool)
    line_delta = st_line - vwap
    mask = (
        valid
        & (line_delta.shift(1) < 0)
        & (line_delta >= 0)
        & bullish
        & (close >= vwap)
    )
    hits = list(mask[mask.fillna(False)].index)
    cross_time = hits[-1] if hits else None
    age = (
        max(0.0, (latest_source_time - cross_time).total_seconds())
        if cross_time is not None and latest_source_time is not None
        else None
    )

    latest_st = gs455._finite(st_line.iloc[-1]) if len(st_line) else None
    latest_vwap = gs455._finite(vwap.iloc[-1]) if len(vwap) else None
    latest_close = gs455._finite(close.iloc[-1]) if len(close) else None
    current_confirmed = bool(
        latest_st is not None
        and latest_vwap is not None
        and latest_close is not None
        and bool(bullish.iloc[-1])
        and latest_close >= latest_vwap
        and latest_st >= latest_vwap
    )

    event = {
        "timeframe": label,
        "crossed": cross_time is not None,
        "recent": bool(
            age is not None
            and age <= gs455._RECENT_WINDOWS_SECONDS[label]
        ),
        "new": bool(
            age is not None
            and age <= gs455._NEW_WINDOWS_SECONDS[label]
        ),
        "timestamp": (
            cross_time.isoformat()
            if cross_time is not None
            else None
        ),
        "age_seconds": (
            round(age, 1)
            if age is not None
            else None
        ),
        "current_confirmed": current_confirmed,
        "latest_supertrend_value": (
            round(latest_st, 6)
            if latest_st is not None
            else None
        ),
        "latest_vwap_value": (
            round(latest_vwap, 6)
            if latest_vwap is not None
            else None
        ),
    }
    if cross_time is not None:
        event.update(
            {
                "supertrend_value": round(
                    float(st_line.loc[cross_time]),
                    6,
                ),
                "vwap_value": round(
                    float(vwap.loc[cross_time]),
                    6,
                ),
                "price": round(
                    float(close.loc[cross_time]),
                    6,
                ),
                "volume": round(
                    float(frame.loc[cross_time, "volume"]),
                    2,
                ),
            }
        )
    return event


def maturation_confirmation_details_with_line_cross(
    day,
    primary_series,
) -> tuple[int, dict]:
    """GS423 confirmation pass plus literal cross metadata, with no extra ST call."""
    from mide import gs378_live_vwap_st_crossover as gs378
    from mide import gs455_early_ignition_3m_confirmation as gs455

    confirmations = 0
    details: dict[str, dict] = {}
    latest_source_time = (
        day.index[-1]
        if day is not None and not day.empty
        else None
    )

    for label in ("1m", "3m", "5m", "10m"):
        tf = gs378._timeframe_frame(day, label)
        if len(tf) < 20:
            continue
        vwap = gs378._timeframe_vwap(
            primary_series,
            label,
        ).reindex(tf.index)
        st_line, trend = gs378.supertrend(
            tf,
            10,
            3,
        )
        close = tf["close"].astype(float)
        latest_vwap = (
            gs378._finite_number(vwap.iloc[-1])
            if len(vwap)
            else None
        )
        latest_close = (
            gs378._finite_number(close.iloc[-1])
            if len(close)
            else None
        )
        bullish = bool(
            len(trend) and trend.iloc[-1]
        )
        above_vwap = bool(
            latest_vwap is not None
            and latest_close is not None
            and latest_close >= latest_vwap
        )
        if bullish and above_vwap:
            confirmations += 1

        valid = st_line.notna() & vwap.notna()
        bullish_series = (
            trend.fillna(False).astype(bool)
        )
        prior_bullish = (
            bullish_series.shift(1)
            .fillna(False)
            .astype(bool)
        )
        flip_mask = (
            valid
            & bullish_series
            & (~prior_bullish)
            & (close >= vwap)
        )
        flip_time = gs378._latest_event(
            flip_mask
        )
        flip_age = (
            max(
                0.0,
                (
                    latest_source_time
                    - flip_time
                ).total_seconds(),
            )
            if (
                flip_time is not None
                and latest_source_time is not None
            )
            else None
        )

        detail = {
            "above_vwap": above_vwap,
            "supertrend": bullish,
            "timeframe": label,
            "data_available": bool(valid.any()),
            "current_supertrend_bullish": bullish,
            "current_above_vwap": above_vwap,
            "current_confirmed": bool(
                bullish and above_vwap
            ),
            "current_close": latest_close,
            "current_vwap": latest_vwap,
            "bullish_flip_timestamp": (
                flip_time.isoformat()
                if flip_time is not None
                else None
            ),
            "bullish_flip_age_seconds": (
                round(flip_age, 1)
                if flip_age is not None
                else None
            ),
            "st_vwap_line_cross": (
                gs455._line_cross_event(
                    tf,
                    vwap,
                    st_line,
                    trend,
                    label,
                    latest_source_time=latest_source_time,
                )
            ),
        }
        if flip_time is not None:
            flip_price = gs455._finite(
                close.loc[flip_time]
            )
            flip_vwap = gs455._finite(
                vwap.loc[flip_time]
            )
            detail.update(
                {
                    "price_at_flip": flip_price,
                    "vwap_at_flip": flip_vwap,
                    "vwap_distance_at_flip_pct": (
                        round(
                            (
                                flip_price
                                - flip_vwap
                            )
                            / flip_vwap
                            * 100.0,
                            4,
                        )
                        if (
                            flip_price is not None
                            and flip_vwap
                            not in (None, 0)
                        )
                        else None
                    ),
                    "supertrend_at_flip": (
                        gs455._finite(
                            st_line.loc[flip_time]
                        )
                    ),
                    "volume_at_flip": (
                        gs455._finite(
                            tf.loc[
                                flip_time,
                                "volume",
                            ]
                        )
                    ),
                }
            )
        details[label] = detail

    return confirmations, details


def maturation_timeframe_event_with_line_cross(
    day,
    primary_1m,
    label: str,
) -> dict:
    """GS421 timeframe event plus literal cross metadata from the same ST pass."""
    from mide import gs421_multitimeframe_convergence_recorder as gs421
    from mide import gs455_early_ignition_3m_confirmation as gs455
    from mide.indicators import supertrend

    tf = gs421._timeframe_frame(day, label)
    vwap = gs421._timeframe_vwap(
        primary_1m,
        label,
    ).reindex(tf.index)
    if len(tf) < 2 or vwap.empty:
        return {
            "timeframe": label,
            "data_available": False,
            "current_supertrend_bullish": False,
            "current_above_vwap": False,
            "current_confirmed": False,
            "bullish_flip_timestamp": None,
            "bullish_flip_age_seconds": None,
            "st_vwap_line_cross": {
                "timeframe": label,
                "crossed": False,
                "recent": False,
                "new": False,
                "timestamp": None,
                "age_seconds": None,
                "current_confirmed": False,
            },
        }

    st_line, trend = supertrend(tf, 10, 3)
    bullish = trend.fillna(False).astype(bool)
    prior_bullish = (
        bullish.shift(1)
        .fillna(False)
        .astype(bool)
    )
    close = tf["close"].astype(float)
    valid = st_line.notna() & vwap.notna()
    flip_mask = (
        valid
        & bullish
        & (~prior_bullish)
        & (close >= vwap)
    )
    hits = list(flip_mask[flip_mask].index)
    flip_time = hits[-1] if hits else None

    latest_vwap = (
        gs455._finite(vwap.iloc[-1])
        if len(vwap)
        else None
    )
    latest_close = gs455._finite(
        close.iloc[-1]
    )
    current_bullish = bool(
        len(bullish) and bullish.iloc[-1]
    )
    current_above_vwap = bool(
        latest_close is not None
        and latest_vwap is not None
        and latest_close >= latest_vwap
    )

    event = {
        "timeframe": label,
        "data_available": bool(valid.any()),
        "current_supertrend_bullish": current_bullish,
        "current_above_vwap": current_above_vwap,
        "current_confirmed": bool(
            current_bullish
            and current_above_vwap
        ),
        "current_close": latest_close,
        "current_vwap": latest_vwap,
        "bullish_flip_timestamp": (
            flip_time.isoformat()
            if flip_time is not None
            else None
        ),
        "bullish_flip_age_seconds": None,
        "st_vwap_line_cross": (
            gs455._line_cross_event(
                tf,
                vwap,
                st_line,
                trend,
                label,
                latest_source_time=day.index[-1],
            )
        ),
    }
    if flip_time is not None:
        age = max(
            0.0,
            (
                day.index[-1]
                - flip_time
            ).total_seconds(),
        )
        flip_price = gs455._finite(
            close.loc[flip_time]
        )
        flip_vwap = gs455._finite(
            vwap.loc[flip_time]
        )
        event.update(
            {
                "bullish_flip_age_seconds": round(
                    age,
                    1,
                ),
                "price_at_flip": flip_price,
                "vwap_at_flip": flip_vwap,
                "vwap_distance_at_flip_pct": (
                    round(
                        (
                            flip_price
                            - flip_vwap
                        )
                        / flip_vwap
                        * 100.0,
                        4,
                    )
                    if (
                        flip_price is not None
                        and flip_vwap
                        not in (None, 0)
                    )
                    else None
                ),
                "supertrend_at_flip": (
                    gs455._finite(
                        st_line.loc[flip_time]
                    )
                ),
                "volume_at_flip": (
                    gs455._finite(
                        tf.loc[
                            flip_time,
                            "volume",
                        ]
                    )
                ),
            }
        )
    return event


def install_maturation_line_cross_enrichment() -> None:
    """Converge GS423 first, then enrich its already-paid ST passes."""
    from mide import gs378_live_vwap_st_crossover as gs378
    from mide import gs421_multitimeframe_convergence_recorder as gs421
    from mide import gs423_convergence_handoff_efficiency as gs423
    from mide import gs455_early_ignition_3m_confirmation as gs455

    gs423.install()

    current_confirmation = (
        gs455._confirmation_details_with_line_cross
    )
    if not getattr(
        gs378._confirmation_details,
        "_gs455_line_cross",
        False,
    ):
        current_confirmation._gs455_line_cross = True
        current_confirmation._gs455_original = (
            gs378._confirmation_details
        )
        gs378._confirmation_details = (
            current_confirmation
        )

    current_timeframe = (
        gs455._timeframe_event_with_line_cross
    )
    if not getattr(
        gs421._timeframe_event,
        "_gs455_line_cross",
        False,
    ):
        current_timeframe._gs455_line_cross = True
        current_timeframe._gs455_original = (
            gs421._timeframe_event
        )
        gs421._timeframe_event = (
            current_timeframe
        )


# ---------------------------------------------------------------------------
# GS460/GS461 ST compression + cascade runway market evidence
# ---------------------------------------------------------------------------

ST_FLIP_EARLY_LADDER = ("30s", "1m", "3m", "5m")
_ST_FLIP_LATER_CONTEXT = ("10m", "15m")
_ST_FLIP_RECENT_SECONDS = {
    "30s": 12 * 60.0,
    "1m": 18 * 60.0,
    "3m": 28 * 60.0,
    "5m": 40 * 60.0,
}
_ST_FLIP_NEW_SECONDS = {
    "30s": 90.0,
    "1m": 120.0,
    "3m": 240.0,
    "5m": 360.0,
}
_ST_FLIP_MAX_CLUSTER_SPAN_PCT = {2: 5.0, 3: 7.0, 4: 9.0}

CASCADE_RUNWAY_ORDER = ("10m", "15m", "30m", "1h")
_CASCADE_RUNWAY_RULES = {
    "10m": "10min",
    "15m": "15min",
    "30m": "30min",
    "1h": "60min",
}
CASCADE_RUNWAY_AUTHORITY = "OPERATOR_ATTENTION_ONLY"
CASCADE_RUNWAY_SOURCE = (
    "existing GS460/GS423 evidence + local resample of already-fetched "
    "current-session 1m bars"
)


def st_flip_number(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def st_flip_timeframe_detail(record: dict, label: str) -> dict:
    if label == "30s":
        tripwire = dict(record.get("thirty_second_tripwire") or {})
        return {
            "timeframe": "30s",
            "price_at_flip": (
                st_flip_number(record.get("supertrend_30s_last_flip_price"))
                or st_flip_number(tripwire.get("last_flip_price"))
            ),
            "age_seconds": (
                st_flip_number(record.get("supertrend_30s_last_flip_age_seconds"))
                if record.get("supertrend_30s_last_flip_age_seconds") is not None
                else st_flip_number(tripwire.get("last_flip_age_seconds"))
            ),
            "current_bullish": bool(
                record.get("supertrend_30s_bullish")
                or tripwire.get("bullish")
                or tripwire.get("supertrend_bullish")
            ),
            "timestamp": (
                record.get("supertrend_30s_last_flip_timestamp")
                or tripwire.get("last_flip_timestamp")
            ),
        }

    timeframes = record.get("timeframes") or {}
    detail = dict(timeframes.get(label) or {})
    if label == "15m" and not detail:
        maturation = record.get("multitimeframe_maturation") or {}
        detail = dict((maturation.get("timeframes") or {}).get(label) or {})
    return {
        "timeframe": label,
        "price_at_flip": st_flip_number(detail.get("price_at_flip")),
        "age_seconds": st_flip_number(detail.get("bullish_flip_age_seconds")),
        "current_bullish": bool(
            detail.get("current_supertrend_bullish")
            or detail.get("supertrend")
        ),
        "timestamp": detail.get("bullish_flip_timestamp"),
        "current_close": st_flip_number(detail.get("current_close")),
        "line_cross": dict(detail.get("st_vwap_line_cross") or {}),
    }


def st_flip_consecutive_recent_rungs(record: dict) -> list[dict]:
    """Return the consecutive bullish 30s->5m flip sequence that is still recent."""
    rungs: list[dict] = []
    for label in ST_FLIP_EARLY_LADDER:
        detail = st_flip_timeframe_detail(record, label)
        price = detail.get("price_at_flip")
        age = detail.get("age_seconds")
        if (
            price is None
            or price <= 0
            or age is None
            or age < 0
            or age > _ST_FLIP_RECENT_SECONDS[label]
            or not detail.get("current_bullish")
        ):
            break
        rungs.append(detail)
    return rungs


def st_flip_cluster_span_pct(prices: list[float]) -> float | None:
    if len(prices) < 2:
        return None
    center = median(prices)
    if center <= 0:
        return None
    return (max(prices) - min(prices)) / center * 100.0


def st_flip_supporting_flow(record: dict) -> bool:
    from mide import gs455_early_ignition_3m_confirmation as gs455

    return bool(gs455._supporting_flow(record))


def st_flip_next_frame_context(record: dict, depth: int) -> dict:
    """Describe the next slower chart without making it part of signal authority."""
    if depth < 2:
        return {}
    next_label = {2: "3m", 3: "5m", 4: "10m"}.get(depth)
    if not next_label:
        return {}
    detail = st_flip_timeframe_detail(record, next_label)
    line_cross = detail.get("line_cross") or {}
    current_close = detail.get("current_close")
    st_value = st_flip_number(line_cross.get("latest_supertrend_value"))
    gap = None
    if current_close not in (None, 0) and st_value is not None:
        gap = abs(st_value - current_close) / current_close * 100.0
    return {
        "timeframe": next_label,
        "already_bullish": bool(detail.get("current_bullish")),
        "distance_to_supertrend_pct": round(gap, 3) if gap is not None else None,
    }


def st_flip_compression(record: dict) -> dict:
    """Return bottom-up flip-price compression evidence for operator attention."""
    rungs = st_flip_consecutive_recent_rungs(record)
    depth = len(rungs)
    prices = [float(item["price_at_flip"]) for item in rungs]
    span = st_flip_cluster_span_pct(prices)
    limit = _ST_FLIP_MAX_CLUSTER_SPAN_PCT.get(depth)
    compressed = bool(
        depth >= 2
        and span is not None
        and limit is not None
        and span <= limit
    )
    flow = st_flip_supporting_flow(record)
    active = bool(compressed and flow)

    highest = rungs[-1] if rungs else {}
    highest_label = str(highest.get("timeframe") or "")
    highest_age = st_flip_number(highest.get("age_seconds"))
    fresh_join = bool(
        active
        and highest_label in _ST_FLIP_NEW_SECONDS
        and highest_age is not None
        and highest_age <= _ST_FLIP_NEW_SECONDS[highest_label]
    )

    stage = {
        0: "NONE",
        1: "SEED",
        2: "EARLY IGNITION",
        3: "IGNITION BUILDING",
        4: "IGNITION CASCADE",
    }.get(depth, "NONE")
    later_bullish = [
        label
        for label in _ST_FLIP_LATER_CONTEXT
        if st_flip_timeframe_detail(record, label).get("current_bullish")
    ]

    return {
        "active": active,
        "fresh_join": fresh_join,
        "stage": stage,
        "depth": depth,
        "sequence": " -> ".join(item["timeframe"] for item in rungs),
        "flip_prices": {
            item["timeframe"]: round(float(item["price_at_flip"]), 6)
            for item in rungs
        },
        "cluster_span_pct": round(span, 3) if span is not None else None,
        "cluster_limit_pct": limit,
        "supporting_flow": flow,
        "highest_rung": highest_label or None,
        "highest_rung_age_seconds": highest_age,
        "next_frame": st_flip_next_frame_context(record, depth),
        "later_bullish_context": later_bullish,
        "authority": "OPERATOR_ATTENTION_ONLY",
        "entry_authority_changed": False,
    }


def cascade_runway_number(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if pd.notna(number) else None


def cascade_runway_status_payload(
    label: str,
    *,
    available: bool,
    bullish: bool = False,
    close: float | None = None,
    supertrend_value: float | None = None,
    source: str,
) -> dict:
    close = cascade_runway_number(close)
    st_value = cascade_runway_number(supertrend_value)
    gap = None
    if available and close not in (None, 0) and st_value is not None:
        gap = abs(st_value - close) / close * 100.0
    return {
        "timeframe": label,
        "available": bool(available),
        "bullish": bool(bullish) if available else False,
        "current_close": close,
        "current_supertrend": st_value,
        "line_gap_pct": round(gap, 3) if gap is not None else None,
        "barrier_gap_pct": (
            0.0
            if available and bullish
            else round(gap, 3) if gap is not None else None
        ),
        "relation": (
            "support"
            if available and bullish
            else "overhead_barrier" if available else "unavailable"
        ),
        "source": source,
    }


def cascade_runway_existing_status(record: dict, label: str) -> dict | None:
    """Reuse current 10m/15m line truth when GS455/423 already retained it."""
    from mide import gs460_st_flip_compression_ignition as gs460

    if label not in {"10m", "15m"}:
        return None
    detail = gs460._tf_detail(record, label)
    if not detail:
        return None
    line_cross = dict(detail.get("line_cross") or {})
    close = cascade_runway_number(detail.get("current_close"))
    st_value = cascade_runway_number(
        line_cross.get("latest_supertrend_value")
    )
    bullish = bool(detail.get("current_bullish"))
    if bullish and close is not None:
        return cascade_runway_status_payload(
            label,
            available=True,
            bullish=True,
            close=close,
            supertrend_value=st_value,
            source="retained GS455/423 timeframe evidence",
        )
    if close is not None and st_value is not None:
        return cascade_runway_status_payload(
            label,
            available=True,
            bullish=False,
            close=close,
            supertrend_value=st_value,
            source="retained GS455/423 timeframe evidence",
        )
    return None


def cascade_runway_local_status(
    day: pd.DataFrame,
    label: str,
    *,
    resample_fn=None,
    supertrend_fn=None,
) -> dict:
    """Build one slower-frame status locally from already-owned 1m history."""
    if resample_fn is None or supertrend_fn is None:
        from mide.indicators import resample_ohlcv, supertrend

        resample_fn = resample_fn or resample_ohlcv
        supertrend_fn = supertrend_fn or supertrend

    if day is None or day.empty:
        return cascade_runway_status_payload(
            label,
            available=False,
            source="no current-session history",
        )
    rule = _CASCADE_RUNWAY_RULES[label]
    try:
        frame = resample_fn(day, rule)
    except Exception:
        return cascade_runway_status_payload(
            label,
            available=False,
            source=f"local {rule} resample failed",
        )
    if frame is None or frame.empty or len(frame) < 2:
        return cascade_runway_status_payload(
            label,
            available=False,
            source=f"local {rule} resample not ready",
        )

    try:
        st_line, trend = supertrend_fn(frame, 10, 3)
    except Exception:
        return cascade_runway_status_payload(
            label,
            available=False,
            source=f"local {rule} SuperTrend not ready",
        )

    close = cascade_runway_number(frame["close"].astype(float).iloc[-1])
    st_value = (
        cascade_runway_number(st_line.iloc[-1])
        if len(st_line)
        else None
    )
    if close is None or st_value is None or not len(trend):
        return cascade_runway_status_payload(
            label,
            available=False,
            source=f"local {rule} SuperTrend not ready",
        )
    return cascade_runway_status_payload(
        label,
        available=True,
        bullish=bool(trend.fillna(False).astype(bool).iloc[-1]),
        close=close,
        supertrend_value=st_value,
        source=(
            f"local {rule} resample from Stage-6 "
            "current-session 1m history"
        ),
    )


def summarize_cascade_runway(
    compression: dict,
    statuses: dict[str, dict],
) -> dict:
    """Summarize the factual slower-frame path without a probability model."""
    ordered = [
        dict(statuses.get(label) or {})
        for label in CASCADE_RUNWAY_ORDER
    ]
    available = [
        item["timeframe"]
        for item in ordered
        if item.get("available")
    ]
    bullish = [
        item["timeframe"]
        for item in ordered
        if item.get("available") and item.get("bullish")
    ]

    contiguous: list[str] = []
    first_unresolved: dict | None = None
    first_index: int | None = None
    for index, item in enumerate(ordered):
        if item.get("available") and item.get("bullish"):
            if first_unresolved is None:
                contiguous.append(item["timeframe"])
            continue
        first_unresolved = item
        first_index = index
        break

    future_support: list[str] = []
    if first_index is not None:
        future_support = [
            item["timeframe"]
            for item in ordered[first_index + 1 :]
            if item.get("available") and item.get("bullish")
        ]

    next_barrier = None
    blocked_by_unavailable = None
    if first_unresolved:
        if (
            first_unresolved.get("available")
            and not first_unresolved.get("bullish")
        ):
            next_barrier = {
                "timeframe": first_unresolved.get("timeframe"),
                "barrier_gap_pct": first_unresolved.get(
                    "barrier_gap_pct"
                ),
                "current_close": first_unresolved.get("current_close"),
                "current_supertrend": first_unresolved.get(
                    "current_supertrend"
                ),
            }
        elif not first_unresolved.get("available"):
            blocked_by_unavailable = first_unresolved.get("timeframe")

    active = bool(compression.get("active") and available)
    return {
        "active": active,
        "lower_stage": compression.get("stage"),
        "lower_depth": int(compression.get("depth") or 0),
        "lower_sequence": compression.get("sequence") or "",
        "frames": {
            item.get("timeframe"): item
            for item in ordered
            if item.get("timeframe")
        },
        "available_frames": available,
        "bullish_frames": bullish,
        "contiguous_slower_bullish": contiguous,
        "next_barrier": next_barrier,
        "blocked_by_unavailable": blocked_by_unavailable,
        "future_bullish_support": future_support,
        "authority": CASCADE_RUNWAY_AUTHORITY,
        "source": CASCADE_RUNWAY_SOURCE,
        "additional_history_requests": 0,
        "entry_authority_changed": False,
    }


def build_cascade_runway(record: dict, raw_rows, client) -> dict:
    """Build slower-frame runway only after GS460 compression is active."""
    from mide import gs378_live_vwap_st_crossover as gs378
    from mide import gs460_st_flip_compression_ignition as gs460
    from mide import gs461_cascade_runway as gs461

    compression = gs460.st_flip_compression(record)
    if not compression.get("active"):
        return {
            "active": False,
            "reason": "no_active_gs460_compression",
            "authority": CASCADE_RUNWAY_AUTHORITY,
            "source": CASCADE_RUNWAY_SOURCE,
            "additional_history_requests": 0,
            "entry_authority_changed": False,
        }

    try:
        frame = client.bars_frame(raw_rows or [])
        day = gs378._eastern_day(frame)
    except Exception:
        day = pd.DataFrame()

    statuses: dict[str, dict] = {}
    for label in CASCADE_RUNWAY_ORDER:
        existing = cascade_runway_existing_status(record, label)
        statuses[label] = (
            existing
            if existing is not None
            else gs461._local_status(day, label)
        )
    return summarize_cascade_runway(compression, statuses)


def install_cascade_runway_evidence() -> None:
    """Attach GS461 runway evidence without adding provider work."""
    from mide import gs378_live_vwap_st_crossover as gs378

    current = gs378.apply_live_vwap_truth
    if getattr(current, "_gs461_cascade_runway", False):
        return

    @wraps(current)
    def apply_with_runway(
        records,
        current_session_raw,
        current_session_30s_raw,
        client,
    ):
        from mide import gs461_cascade_runway as gs461

        updated = current(
            records,
            current_session_raw,
            current_session_30s_raw,
            client,
        )
        measured = 0
        for record in updated or []:
            symbol = str(record.get("symbol") or "").strip().upper()
            if not symbol:
                continue
            evidence = gs461.build_cascade_runway(
                record,
                (current_session_raw or {}).get(symbol) or [],
                client,
            )
            if evidence.get("active"):
                record["st_cascade_runway"] = evidence
                measured += 1

        diagnostics = getattr(client, "diagnostics", None)
        if isinstance(diagnostics, dict):
            diagnostics["gs461_cascade_runway"] = {
                "authority": CASCADE_RUNWAY_AUTHORITY,
                "records_measured": measured,
                "timeframes": list(CASCADE_RUNWAY_ORDER),
                "additional_history_requests": 0,
                "entry_authority_changed": False,
                "qualification_changed": False,
                "readiness_changed": False,
                "execution_changed": False,
            }
        return updated

    apply_with_runway._gs461_cascade_runway = True
    apply_with_runway._gs461_original = current
    gs378.apply_live_vwap_truth = apply_with_runway


# ---------------------------------------------------------------------------
# GS478 sparse current-session history sufficiency bridge
# ---------------------------------------------------------------------------

SPARSE_HISTORY_AUTHORITY = "HISTORY_SUFFICIENCY_BRIDGE_ONLY"
SPARSE_HISTORY_CURRENT_REASON = "stage6_current_session"
SPARSE_HISTORY_BRIDGE_REASON = "stage6_sparse_history_bridge"
SPARSE_HISTORY_MIN_REAL_SESSION_BARS = 12
SPARSE_HISTORY_LEGACY_OUTER_GATE_BARS = 20
SPARSE_HISTORY_LOOKBACK_DAYS = 14
SPARSE_HISTORY_BAR_LIMIT = 32
_SPARSE_HISTORY_OWNER = "_walter_gs478_sparse_history_bridge_owner"


def sparse_history_symbols(values) -> list[str]:
    return list(
        dict.fromkeys(
            str(value or "").strip().upper()
            for value in values or []
            if str(value or "").strip()
        )
    )


def sparse_history_frame(client, rows) -> pd.DataFrame:
    try:
        frame = client.bars_frame(list(rows or []))
    except Exception:
        return pd.DataFrame()
    if frame is None or getattr(frame, "empty", True):
        return pd.DataFrame()
    return frame.sort_index()


def sparse_history_current_bar_count(client, rows) -> int:
    frame = sparse_history_frame(client, rows)
    if frame.empty:
        return 0
    latest_date = frame.index[-1].date()
    return int((frame.index.date == latest_date).sum())


def bridge_sparse_history_rows(
    client,
    prior_rows,
    current_rows,
) -> tuple[list[dict], int]:
    """Prepend only enough genuine prior rows to clear the obsolete 20-row guard."""
    current = list(current_rows or [])
    current_count = sparse_history_current_bar_count(client, current)
    if not (
        SPARSE_HISTORY_MIN_REAL_SESSION_BARS
        <= current_count
        < SPARSE_HISTORY_LEGACY_OUTER_GATE_BARS
    ):
        return current, 0

    prior = list(prior_rows or [])
    needed = SPARSE_HISTORY_LEGACY_OUTER_GATE_BARS - current_count
    if len(prior) < needed:
        return current, 0
    return prior[-needed:] + current, needed


def install_sparse_history_bridge() -> None:
    """Bridge only the validated 12-19 real-bar Stage-6 sufficiency mismatch."""
    from mide import discovery

    current_analyze = discovery.analyze_candidates
    if getattr(current_analyze, _SPARSE_HISTORY_OWNER, False):
        return

    @wraps(current_analyze)
    def analyze_with_sparse_history_bridge(
        client,
        candidates,
        news_index,
        discovery_reasons,
    ):
        from mide import gs478_sparse_history_warm_seed as gs478

        original_bars = getattr(client, "bars", None)
        if not callable(original_bars):
            return current_analyze(
                client,
                candidates,
                news_index,
                discovery_reasons,
            )

        bridged: dict[str, int] = {}
        sparse_counts: dict[str, int] = {}
        under_minimum: dict[str, int] = {}
        bridge_request_count = 0
        had_instance_bars = False
        prior_instance_bars: Any = None
        instance_dict = getattr(client, "__dict__", None)
        if isinstance(instance_dict, dict):
            had_instance_bars = "bars" in instance_dict
            prior_instance_bars = instance_dict.get("bars")

        def bridge_bars(symbols, **kwargs):
            nonlocal bridge_request_count
            wanted = gs478._symbols(symbols)
            result = original_bars(wanted, **kwargs)
            reason = str(kwargs.get("history_reason") or "")
            timeframe = str(kwargs.get("timeframe") or "").strip().lower()
            if (
                reason != gs478.CURRENT_REASON
                or timeframe not in {"1min", "1m", "m1"}
            ):
                return result

            result = dict(result or {})
            bridge_symbols = []
            for symbol in wanted:
                count = gs478._current_bar_count(
                    client,
                    result.get(symbol) or [],
                )
                if 0 < count < gs478.MIN_REAL_SESSION_BARS:
                    under_minimum[symbol] = count
                elif (
                    gs478.MIN_REAL_SESSION_BARS
                    <= count
                    < gs478.LEGACY_OUTER_GATE_BARS
                ):
                    sparse_counts[symbol] = count
                    bridge_symbols.append(symbol)

            if not bridge_symbols:
                return result

            try:
                session_start = pd.Timestamp(kwargs.get("start"))
            except Exception:
                return result
            if session_start.tzinfo is None:
                session_start = session_start.tz_localize("America/New_York")

            bridge_kwargs = {
                "start": (
                    session_start - timedelta(days=gs478.BRIDGE_LOOKBACK_DAYS)
                ).to_pydatetime(),
                "end": session_start.to_pydatetime(),
                "timeframe": "1Min",
                "limit": gs478.BRIDGE_HISTORY_BARS,
                "force_batch": True,
                "history_reason": gs478.BRIDGE_REASON,
            }
            try:
                prior = original_bars(bridge_symbols, **bridge_kwargs) or {}
                bridge_request_count += 1
            except Exception as exc:
                warnings = getattr(client, "warnings", None)
                if isinstance(warnings, list):
                    warnings.append(
                        f"Sparse Stage-6 history bridge unavailable: {exc}"
                    )
                prior = {}

            for symbol in bridge_symbols:
                merged, used = gs478._bridge_rows(
                    client,
                    (prior or {}).get(symbol) or [],
                    result.get(symbol) or [],
                )
                if used:
                    result[symbol] = merged
                    bridged[symbol] = used
            return result

        patched = False
        try:
            setattr(client, "bars", bridge_bars)
            patched = True
            records = current_analyze(
                client,
                candidates,
                news_index,
                discovery_reasons,
            )
        finally:
            if patched:
                try:
                    if had_instance_bars:
                        setattr(client, "bars", prior_instance_bars)
                    else:
                        delattr(client, "bars")
                except Exception:
                    try:
                        setattr(client, "bars", original_bars)
                    except Exception:
                        pass

        diagnostics = getattr(client, "diagnostics", None)
        if isinstance(diagnostics, dict):
            diagnostics["gs478_sparse_history_bridge"] = {
                "authority": SPARSE_HISTORY_AUTHORITY,
                "sparse_current_bar_counts": dict(
                    sorted(sparse_counts.items())
                ),
                "bridged_prior_rows": dict(sorted(bridged.items())),
                "below_safe_minimum_counts": dict(
                    sorted(under_minimum.items())
                ),
                "bridge_history_requests": bridge_request_count,
                "bridge_history_bar_limit": SPARSE_HISTORY_BAR_LIMIT,
                "minimum_real_session_bars": (
                    SPARSE_HISTORY_MIN_REAL_SESSION_BARS
                ),
                "legacy_outer_gate_bars": (
                    SPARSE_HISTORY_LEGACY_OUTER_GATE_BARS
                ),
                "synthetic_bars": 0,
                "volume_profile_contract_changed": False,
                "thirty_second_history_added": False,
                "trading_logic_changed": False,
            }
        return records

    for name, value in getattr(current_analyze, "__dict__", {}).items():
        if name.startswith("_gs") and not hasattr(
            analyze_with_sparse_history_bridge,
            name,
        ):
            setattr(analyze_with_sparse_history_bridge, name, value)
    analyze_with_sparse_history_bridge._gs478_sparse_history_bridge = True
    analyze_with_sparse_history_bridge._gs478_original = current_analyze
    setattr(
        analyze_with_sparse_history_bridge,
        _SPARSE_HISTORY_OWNER,
        True,
    )
    discovery.analyze_candidates = analyze_with_sparse_history_bridge


# ---------------------------------------------------------------------------
# GS423 efficient multitimeframe convergence evidence
# ---------------------------------------------------------------------------

CONVERGENCE_HANDOFF_AUTHORITY = "OBSERVATIONAL_ONLY"
CONVERGENCE_HANDOFF_SOURCE = (
    "GS378 already-computed 1m/3m/5m/10m state plus one local 15m maturation pass; "
    "no additional provider history request"
)
_CONVERGENCE_HANDOFF_INSTALL_GENERATION = object()


def _convergence_number(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if pd.notna(number) else None


def confirmation_details_with_maturation(
    day: pd.DataFrame,
    primary_series: pd.Series,
) -> tuple[int, dict]:
    """Preserve GS378 confirmation truth while retaining already-computed flip data."""
    from mide import gs378_live_vwap_st_crossover as gs378

    confirmations = 0
    details: dict[str, dict] = {}
    latest_source_time = day.index[-1] if day is not None and not day.empty else None

    for label in ("1m", "3m", "5m", "10m"):
        tf = gs378._timeframe_frame(day, label)
        if len(tf) < 20:
            continue
        vwap = gs378._timeframe_vwap(primary_series, label).reindex(tf.index)
        st_line, trend = gs378.supertrend(tf, 10, 3)
        close = tf["close"].astype(float)
        latest_vwap = gs378._finite_number(vwap.iloc[-1]) if len(vwap) else None
        latest_close = gs378._finite_number(close.iloc[-1]) if len(close) else None
        bullish = bool(len(trend) and trend.iloc[-1])
        above_vwap = bool(
            latest_vwap is not None
            and latest_close is not None
            and latest_close >= latest_vwap
        )
        if bullish and above_vwap:
            confirmations += 1

        valid = st_line.notna() & vwap.notna()
        bullish_series = trend.fillna(False).astype(bool)
        prior_bullish = bullish_series.shift(1).fillna(False).astype(bool)
        flip_mask = valid & bullish_series & (~prior_bullish) & (close >= vwap)
        flip_time = gs378._latest_event(flip_mask)
        flip_age = (
            max(0.0, (latest_source_time - flip_time).total_seconds())
            if flip_time is not None and latest_source_time is not None
            else None
        )

        detail = {
            "above_vwap": above_vwap,
            "supertrend": bullish,
            "timeframe": label,
            "data_available": bool(valid.any()),
            "current_supertrend_bullish": bullish,
            "current_above_vwap": above_vwap,
            "current_confirmed": bool(bullish and above_vwap),
            "current_close": latest_close,
            "current_vwap": latest_vwap,
            "bullish_flip_timestamp": (
                flip_time.isoformat() if flip_time is not None else None
            ),
            "bullish_flip_age_seconds": (
                round(flip_age, 1) if flip_age is not None else None
            ),
        }
        if flip_time is not None:
            flip_price = _convergence_number(close.loc[flip_time])
            flip_vwap = _convergence_number(vwap.loc[flip_time])
            detail.update(
                {
                    "price_at_flip": flip_price,
                    "vwap_at_flip": flip_vwap,
                    "vwap_distance_at_flip_pct": (
                        round((flip_price - flip_vwap) / flip_vwap * 100.0, 4)
                        if flip_price is not None and flip_vwap not in (None, 0)
                        else None
                    ),
                    "supertrend_at_flip": _convergence_number(st_line.loc[flip_time]),
                    "volume_at_flip": _convergence_number(tf.loc[flip_time, "volume"]),
                }
            )
        details[label] = detail

    return confirmations, details


def _convergence_fallback_event(record: dict, label: str) -> dict:
    cross = dict((record.get("st_vwap_cross_events") or {}).get(label) or {})
    alignment = dict((record.get("timeframe_alignment") or {}).get(label) or {})
    bullish = bool(alignment.get("supertrend_bullish"))
    above_vwap = bool(alignment.get("above_vwap"))
    return {
        "timeframe": label,
        "data_available": bool(cross or alignment),
        "current_supertrend_bullish": bullish,
        "current_above_vwap": above_vwap,
        "current_confirmed": bool(bullish and above_vwap),
        "bullish_flip_timestamp": cross.get("bullish_flip_timestamp"),
        "bullish_flip_age_seconds": cross.get("bullish_flip_age_seconds"),
        "price_at_flip": None,
        "vwap_at_flip": None,
        "supertrend_at_flip": None,
        "volume_at_flip": None,
    }


def build_efficient_maturation_evidence(record: dict, raw_rows, client) -> dict:
    """Build live maturation evidence with no duplicate fast-timeframe ST passes."""
    from mide import gs378_live_vwap_st_crossover as gs378
    from mide import gs421_multitimeframe_convergence_recorder as gs421
    from mide import gs422_convergence_recorder_performance as gs422

    if not gs422.should_record_maturation(record):
        return gs422.skipped_evidence(record)

    frame = client.bars_frame(raw_rows or [])
    context = gs378.primary_vwap_context(frame)
    day = context.get("day")
    primary = context.get("series")
    if day is None or day.empty or primary is None or primary.empty:
        return {
            "authority": CONVERGENCE_HANDOFF_AUTHORITY,
            "source": CONVERGENCE_HANDOFF_SOURCE,
            "available": False,
            "timeframes": {},
        }

    existing = record.get("timeframes") or {}
    events: dict[str, dict] = {}
    for label in ("1m", "3m", "5m", "10m"):
        detail = existing.get(label)
        if isinstance(detail, dict) and "bullish_flip_timestamp" in detail:
            events[label] = dict(detail)
        elif label in {"1m", "3m"}:
            events[label] = _convergence_fallback_event(record, label)
        else:
            events[label] = {
                "timeframe": label,
                "data_available": False,
                "current_supertrend_bullish": False,
                "current_above_vwap": False,
                "current_confirmed": False,
                "bullish_flip_timestamp": None,
                "bullish_flip_age_seconds": None,
            }

    events["15m"] = gs421._timeframe_event(day, primary, "15m")

    cascade = gs421._cascade(events)
    current_confirmed = [
        label
        for label in gs421.MATURATION_ORDER
        if (events.get(label) or {}).get("current_confirmed")
    ]
    one_minute = events.get("1m") or {}
    return {
        "authority": CONVERGENCE_HANDOFF_AUTHORITY,
        "source": CONVERGENCE_HANDOFF_SOURCE,
        "available": True,
        "model": "30s tripwire -> 1m ignition -> 3m confirmation -> 5m/10m/15m maturation",
        "entry_authority_changed": False,
        "reused_supertrend_timeframes": ["1m", "3m", "5m", "10m"],
        "additional_supertrend_timeframes": ["15m"],
        "additional_history_requests": 0,
        "thirty_second": {
            "investigation_tripwire": bool(record.get("operator_investigation_tripwire")),
            "supertrend_bullish": bool(record.get("supertrend_30s_bullish")),
            "last_flip_timestamp": record.get("supertrend_30s_last_flip_timestamp"),
            "last_flip_age_seconds": _convergence_number(
                record.get("supertrend_30s_last_flip_age_seconds")
            ),
        },
        "timeframes": events,
        "observed_cascade": cascade,
        "cascade_depth": len(cascade),
        "highest_observed_maturation": cascade[-1] if cascade else None,
        "current_confirmed_timeframes": current_confirmed,
        "current_convergence_count": len(current_confirmed),
        "seconds_from_1m_ignition": gs421._delays_from_1m(events),
        "excursion_since_1m_ignition": gs421._excursion_since_1m(day, one_minute),
        "pre_ignition_context": gs421._pre_ignition_context(day, primary, one_minute),
        "scan_snapshot": {
            "price": _convergence_number(record.get("price")),
            "vwap_distance_pct": _convergence_number(record.get("vwap_distance_pct")),
            "participation_score": _convergence_number(record.get("participation_score")),
            "participation_surge_score": _convergence_number(
                record.get("participation_surge_score")
            ),
            "expansion_score": _convergence_number(record.get("expansion_score")),
            "volume_acceleration": _convergence_number(record.get("volume_acceleration")),
            "dollar_flow_acceleration": _convergence_number(
                record.get("dollar_flow_acceleration")
            ),
            "qualified_for_watch": bool(record.get("qualified_for_watch")),
            "qualified_for_entry": bool(record.get("qualified_for_entry")),
            "status": record.get("status"),
        },
    }


def install_convergence_handoff_evidence() -> None:
    """Own GS423's final market-evidence handoff after the GS421/422 chain."""
    from mide import gs378_live_vwap_st_crossover as gs378

    current = gs378.apply_live_vwap_truth
    if (
        getattr(current, "_gs423_install_generation", None)
        is _CONVERGENCE_HANDOFF_INSTALL_GENERATION
    ):
        return

    base = getattr(current, "_gs423_base", None)
    if not callable(base):
        base = getattr(current, "_gs421_original", current)

    gs378._confirmation_details = confirmation_details_with_maturation

    @wraps(base)
    def apply_with_efficient_maturation(
        records,
        current_session_raw,
        current_session_30s_raw,
        client,
    ):
        updated = base(
            records,
            current_session_raw,
            current_session_30s_raw,
            client,
        )
        studied = 0
        skipped = 0
        for record in updated or []:
            symbol = str(record.get("symbol") or "").strip().upper()
            if not symbol:
                continue
            from mide import gs423_convergence_handoff_efficiency as gs423

            evidence = gs423.build_efficient_maturation_evidence(
                record,
                (current_session_raw or {}).get(symbol) or [],
                client,
            )
            record["multitimeframe_maturation"] = evidence
            record["multitimeframe_maturation_authority"] = (
                CONVERGENCE_HANDOFF_AUTHORITY
            )
            if evidence.get("skipped"):
                skipped += 1
            elif evidence.get("available"):
                studied += 1

        diagnostics = getattr(client, "diagnostics", None)
        if isinstance(diagnostics, dict):
            diagnostics["gs423_convergence_handoff_efficiency"] = {
                "authority": CONVERGENCE_HANDOFF_AUTHORITY,
                "records_studied": studied,
                "records_skipped_without_extra_st": skipped,
                "reused_supertrend_timeframes": ["1m", "3m", "5m", "10m"],
                "additional_supertrend_timeframes_per_studied_record": ["15m"],
                "additional_history_requests": 0,
                "entry_authority_changed": False,
                "ranking_changed": False,
                "scoring_changed": False,
                "qualification_changed": False,
            }
        return updated

    for name, value in getattr(base, "__dict__", {}).items():
        if name.startswith("_gs") and not hasattr(apply_with_efficient_maturation, name):
            setattr(apply_with_efficient_maturation, name, value)
    apply_with_efficient_maturation._gs421_multitimeframe_convergence = True
    apply_with_efficient_maturation._gs423_convergence_handoff_efficiency = True
    apply_with_efficient_maturation._gs423_install_generation = (
        _CONVERGENCE_HANDOFF_INSTALL_GENERATION
    )
    apply_with_efficient_maturation._gs423_base = base
    apply_with_efficient_maturation._gs421_original = base
    gs378.apply_live_vwap_truth = apply_with_efficient_maturation



# ---------------------------------------------------------------------------
# GS464 session-aware primary VWAP market evidence
# ---------------------------------------------------------------------------

_SESSION_VWAP_OWNER = "_walter_gs464_session_aware_vwap_owner"
_SESSION_VWAP_APPLY_OWNER = "_walter_gs464_session_aware_vwap_apply_owner"


def session_vwap_finite(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if pd.notna(number) else None


def session_vwap_last(frame: pd.DataFrame) -> float | None:
    if frame is None or frame.empty:
        return None
    from mide.indicators import session_vwap

    series = session_vwap(frame)
    return (
        session_vwap_finite(series.iloc[-1])
        if len(series)
        else None
    )


def session_aware_primary_vwap_context(
    frame: pd.DataFrame | None,
) -> dict:
    """Use 04:00 ET premarket, then reset primary VWAP at 09:30 ET."""
    from mide import gs378_live_vwap_st_crossover as gs378
    from mide import gs464_session_aware_vwap_parity as gs464
    from mide.indicators import session_vwap

    day = gs378._eastern_day(frame)
    if day.empty:
        return {
            "day": day,
            "series": pd.Series(dtype=float),
            "value": None,
            "anchor_mode": "UNAVAILABLE",
            "anchor_time": None,
            "premarket_value": None,
            "rth_value": None,
            "extended_value": None,
            "session_policy": gs464.SESSION_POLICY,
        }

    premarket_start, regular_start = (
        gs378._session_boundaries(day)
    )
    latest = day.index[-1]

    premarket = day[
        (day.index >= premarket_start)
        & (day.index < regular_start)
    ].copy()
    rth = day[day.index >= regular_start].copy()
    extended = day[
        day.index >= premarket_start
    ].copy()

    premarket_value = gs464._last_vwap(premarket)
    rth_value = gs464._last_vwap(rth)
    extended_value = gs464._last_vwap(extended)

    if latest >= regular_start and not rth.empty:
        anchored = rth
        anchor = regular_start
        mode = gs464.RTH_POLICY
    else:
        anchored = day[
            day.index >= premarket_start
        ].copy()
        anchor = premarket_start
        mode = gs464.PREMARKET_POLICY

    if anchored.empty:
        anchored = day.copy()
        anchor = day.index[0]
        mode = "FALLBACK_FIRST_AVAILABLE_BAR"

    primary = session_vwap(anchored)
    value = (
        gs464._finite(primary.iloc[-1])
        if len(primary)
        else None
    )
    return {
        "day": day,
        "series": primary,
        "value": value,
        "anchor_mode": mode,
        "anchor_time": anchor,
        "premarket_value": premarket_value,
        "rth_value": rth_value,
        "extended_value": extended_value,
        "session_policy": gs464.SESSION_POLICY,
    }


def _inherit_session_vwap_wrapper(wrapper, wrapped) -> None:
    for name, value in getattr(
        wrapped,
        "__dict__",
        {},
    ).items():
        if name.startswith("_gs") and not hasattr(
            wrapper,
            name,
        ):
            setattr(wrapper, name, value)


def install_session_aware_primary_vwap() -> None:
    """Bind GS464 as the final primary-VWAP market-evidence authority."""
    from mide import gs378_live_vwap_st_crossover as gs378

    current = gs378.primary_vwap_context
    if getattr(current, _SESSION_VWAP_OWNER, False):
        return

    _inherit_session_vwap_wrapper(
        session_aware_primary_vwap_context,
        current,
    )
    session_aware_primary_vwap_context._gs464_session_aware_vwap_parity = True
    session_aware_primary_vwap_context._gs464_original = current
    setattr(
        session_aware_primary_vwap_context,
        _SESSION_VWAP_OWNER,
        True,
    )
    gs378.primary_vwap_context = (
        session_aware_primary_vwap_context
    )


def install_session_aware_vwap_record_diagnostics() -> None:
    """Attach GS464 policy labels to existing analyzed records only."""
    from mide import gs378_live_vwap_st_crossover as gs378
    from mide import gs464_session_aware_vwap_parity as gs464

    current = gs378.apply_live_vwap_truth
    if getattr(
        current,
        _SESSION_VWAP_APPLY_OWNER,
        False,
    ):
        return

    @wraps(current)
    def apply_session_aware_truth(
        records,
        current_session_raw,
        current_session_30s_raw,
        client,
    ):
        updated = current(
            records,
            current_session_raw,
            current_session_30s_raw,
            client,
        )
        observed = 0
        for record in updated or []:
            mode = str(
                record.get("vwap_anchor_mode") or ""
            )
            if mode not in {
                gs464.PREMARKET_POLICY,
                gs464.RTH_POLICY,
                "FALLBACK_FIRST_AVAILABLE_BAR",
            }:
                continue
            observed += 1
            record["vwap_primary_session_policy"] = (
                gs464.SESSION_POLICY
            )
            record["vwap_bar_timeframe_source"] = (
                f"{getattr(client, 'provider_name', 'market data provider')} "
                "1Min bars; primary VWAP 04:00 ET premarket / "
                "09:30 ET regular-session reset"
            )
            record["extended_vwap_role"] = (
                "diagnostic_only_after_09:30"
            )

        diagnostics = getattr(
            client,
            "diagnostics",
            None,
        )
        if isinstance(diagnostics, dict):
            diagnostics[
                "gs464_session_aware_vwap_parity"
            ] = {
                "primary_vwap_policy": gs464.SESSION_POLICY,
                "premarket_anchor": gs464.PREMARKET_POLICY,
                "rth_anchor": gs464.RTH_POLICY,
                "records_observed": observed,
                "extended_vwap_role": (
                    "diagnostic_only_after_09:30"
                ),
                "additional_market_data_requests": 0,
                "trading_thresholds_changed": False,
            }
        return updated

    _inherit_session_vwap_wrapper(
        apply_session_aware_truth,
        current,
    )
    apply_session_aware_truth._gs464_session_aware_vwap_parity = True
    apply_session_aware_truth._gs464_original = current
    setattr(
        apply_session_aware_truth,
        _SESSION_VWAP_APPLY_OWNER,
        True,
    )
    gs378.apply_live_vwap_truth = (
        apply_session_aware_truth
    )


def install_session_aware_vwap_evidence() -> None:
    """Install all GS464 Market Evidence responsibilities."""
    install_session_aware_primary_vwap()
    install_session_aware_vwap_record_diagnostics()



# ---------------------------------------------------------------------------
# GS469/GS470/GS471 genuine Webull 30-second market-data lifecycle
# ---------------------------------------------------------------------------

def live_30s_utc(value: datetime | None = None) -> datetime:
    if value is None:
        return datetime.now(timezone.utc)
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def live_30s_now_ms(value: datetime | None = None) -> int:
    return int(live_30s_utc(value).timestamp() * 1000)


def live_30s_market_expected(value: datetime | None = None) -> bool:
    from mide import gs469_30s_stream_continuity as gs469
    from mide.time_service import eastern_time

    current = eastern_time(live_30s_utc(value))
    clock = current.time().replace(tzinfo=None)
    return (
        current.weekday() < 5
        and gs469.STREAM_START_ET <= clock < gs469.STREAM_END_ET
    )


def live_30s_stream_diagnostics(provider) -> dict:
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


def live_30s_last_tick_ms(provider) -> int | None:
    raw = live_30s_stream_diagnostics(provider).get(
        "last_tick_timestamp_ms"
    )
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return None
    return value if value > 0 else None


def live_30s_tick_age_seconds(
    provider,
    value: datetime | None = None,
) -> float | None:
    last = live_30s_last_tick_ms(provider)
    if last is None:
        return None
    return max(
        0.0,
        (live_30s_now_ms(value) - last) / 1000.0,
    )


def active_30s_registry_provider():
    from mide import gs379_webull_stream_data_truth as gs379

    reference = getattr(gs379, "_ACTIVE_PROVIDER_REF", None)
    if reference is None:
        return None
    try:
        return reference()
    except TypeError:
        return None


def reassert_active_30s_provider(provider) -> bool:
    if provider is None or not getattr(
        provider,
        "_enable_streaming",
        False,
    ):
        return False
    if active_30s_registry_provider() is provider:
        return False

    from mide import gs379_webull_stream_data_truth as gs379

    gs379._register_active_provider(provider)
    stream = live_30s_stream_diagnostics(provider)
    stream["gs469_active_provider_rebinds"] = int(
        stream.get("gs469_active_provider_rebinds", 0) or 0
    ) + 1
    return True


def live_30s_subscription_started_ms(provider) -> int | None:
    raw = getattr(provider, "_gs469_subscription_started_ms", None)
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return None
    return value if value > 0 else None


def live_30s_restart_cooldown_active(
    provider,
    value: datetime | None = None,
) -> bool:
    from mide import gs469_30s_stream_continuity as gs469

    raw = getattr(provider, "_gs469_last_restart_attempt_ms", None)
    try:
        last = int(raw)
    except (TypeError, ValueError):
        return False
    return (
        live_30s_now_ms(value) - last
    ) / 1000.0 < gs469.RESTART_COOLDOWN_SECONDS


def live_30s_restart_reason(
    provider,
    value: datetime | None = None,
) -> str | None:
    from mide import gs469_30s_stream_continuity as gs469

    if not getattr(provider, "_enable_streaming", False):
        return None
    if not live_30s_market_expected(value):
        return None
    if getattr(provider, "_subscription", None) is None:
        return None
    if not set(getattr(provider, "_subscribed", set()) or set()):
        return None
    if live_30s_restart_cooldown_active(provider, value):
        return None

    age = live_30s_tick_age_seconds(provider, value)
    if age is not None:
        if age > gs469.STALE_TICK_SECONDS:
            return f"last Webull TICK heartbeat is {age:.1f}s old"
        return None

    started = live_30s_subscription_started_ms(provider)
    if started is not None:
        elapsed = max(
            0.0,
            (live_30s_now_ms(value) - started) / 1000.0,
        )
        if elapsed <= gs469.STALE_TICK_SECONDS:
            return None
    return "subscribed Webull transport has no observed TICK heartbeat"


def live_30s_latest_bar_ms(provider) -> int | None:
    latest = None
    current = getattr(provider, "_gs379_30s_current", None)
    if isinstance(current, dict):
        for row in current.values():
            try:
                stamp = int((row or {}).get("t"))
            except (TypeError, ValueError):
                continue
            latest = stamp if latest is None else max(latest, stamp)
    closed = getattr(provider, "_gs379_30s_closed", None)
    if isinstance(closed, dict):
        for rows in closed.values():
            if not rows:
                continue
            try:
                stamp = int((rows[-1] or {}).get("t"))
            except (TypeError, ValueError, KeyError):
                continue
            latest = stamp if latest is None else max(latest, stamp)
    return latest


def clear_prior_session_30s(
    provider,
    value: datetime | None = None,
) -> bool:
    latest = live_30s_latest_bar_ms(provider)
    if latest is None:
        return False

    from mide.time_service import eastern_time

    latest_day = eastern_time(
        datetime.fromtimestamp(
            latest / 1000.0,
            tz=timezone.utc,
        )
    ).date()
    current_day = eastern_time(live_30s_utc(value)).date()
    if latest_day >= current_day:
        return False

    lock = getattr(provider, "_lock", None)
    if lock is None:
        return False
    with lock:
        current = getattr(provider, "_gs379_30s_current", None)
        closed = getattr(provider, "_gs379_30s_closed", None)
        if isinstance(current, dict):
            current.clear()
        if isinstance(closed, dict):
            closed.clear()
    return True


def ensure_live_30s_stream_continuity(
    original,
    provider,
    symbols,
    *,
    now: datetime | None = None,
):
    from mide import gs469_30s_stream_continuity as gs469

    if not getattr(provider, "_enable_streaming", False):
        return original(provider, symbols)

    now = live_30s_utc(now)
    now_ms = live_30s_now_ms(now)
    rebound = gs469.reassert_active_provider(provider)
    reason = live_30s_restart_reason(provider, now)
    restarted = False
    cleared_prior_session = False

    if reason:
        from mide import gs379_webull_stream_data_truth as gs379

        provider._gs469_last_restart_attempt_ms = now_ms
        cleared_prior_session = clear_prior_session_30s(
            provider,
            now,
        )
        gs379._retire_provider_stream(provider)
        restarted = True

    result = original(provider, symbols)

    if getattr(provider, "_subscription", None) is not None:
        if (
            restarted
            or live_30s_subscription_started_ms(provider) is None
        ):
            provider._gs469_subscription_started_ms = now_ms

    stream = live_30s_stream_diagnostics(provider)
    if restarted:
        stream["gs469_stale_stream_restarts"] = int(
            stream.get("gs469_stale_stream_restarts", 0) or 0
        ) + 1
    stream["gs469_30s_stream_continuity"] = {
        "authority": gs469.AUTHORITY,
        "active_provider_reasserted": bool(rebound),
        "stream_expected_now": live_30s_market_expected(now),
        "subscription_present": (
            getattr(provider, "_subscription", None) is not None
        ),
        "subscribed_symbols": len(
            set(getattr(provider, "_subscribed", set()) or set())
        ),
        "last_tick_age_seconds": (
            round(live_30s_tick_age_seconds(provider, now), 1)
            if live_30s_tick_age_seconds(provider, now) is not None
            else None
        ),
        "restart_performed": bool(restarted),
        "restart_reason": reason,
        "prior_session_30s_cleared": bool(cleared_prior_session),
        "restart_cooldown_seconds": gs469.RESTART_COOLDOWN_SECONDS,
        "stale_tick_seconds": gs469.STALE_TICK_SECONDS,
        "genuine_webull_tick_only": True,
        "synthetic_30s_bars": False,
        "entry_authority_changed": False,
    }
    return result


def install_live_30s_stream_continuity() -> None:
    from mide import gs469_30s_stream_continuity as gs469
    from mide import webull_live

    current = webull_live.LiveWebullProvider.ensure_stream
    if getattr(current, gs469._OWNER_ATTR, False):
        return

    @wraps(current)
    def ensure_stream(self, symbols):
        return gs469.ensure_stream_continuity(
            current,
            self,
            symbols,
        )

    ensure_stream._gs469_30s_stream_continuity = True
    ensure_stream._gs469_original = current
    setattr(ensure_stream, gs469._OWNER_ATTR, True)
    webull_live.LiveWebullProvider.ensure_stream = ensure_stream


def production_30s_identity(value: Any) -> tuple[str, str]:
    cls = type(value)
    return (
        str(getattr(cls, "__module__", "")),
        str(getattr(cls, "__name__", "")),
    )


def production_30s_sdk_graph(provider) -> bool:
    if provider is None:
        return False
    snapshot = getattr(provider, "_snapshot_client", None)
    if production_30s_identity(snapshot) != (
        "mide.webull_live",
        "WebullOpenAPIClient",
    ):
        return False
    sdk = getattr(snapshot, "sdk", None)
    if production_30s_identity(sdk) != (
        "mide.webull_sdk",
        "WebullSDKClient",
    ):
        return False
    return (
        getattr(provider, "_stream_class", None) is None
        and getattr(provider, "_bootstrap", None) is None
    )


def ensure_production_30s_state(provider) -> bool:
    lock = getattr(provider, "_lock", None)
    if lock is None:
        return False
    changed = False
    with lock:
        if not isinstance(
            getattr(provider, "_gs379_30s_current", None),
            dict,
        ):
            provider._gs379_30s_current = {}
            changed = True
        if not isinstance(
            getattr(provider, "_gs379_30s_closed", None),
            dict,
        ):
            provider._gs379_30s_closed = {}
            changed = True
    stream = live_30s_stream_diagnostics(provider)
    defaults = {
        "tick_messages_received": 0,
        "tick_symbols_seen": 0,
        "last_tick_timestamp_ms": None,
        "thirty_second_bars_closed": 0,
        "thirty_second_symbols_ready": 0,
        "out_of_order_ticks": 0,
        "unsubscribed_symbols": 0,
        "unsubscribe_failures": 0,
        "stream_replaced_count": 0,
        "stream_cleanup_failures": 0,
        "thirty_second_authority": "OBSERVATIONAL_ONLY",
    }
    for key, default in defaults.items():
        if key not in stream:
            stream[key] = default
            changed = True
    return changed


def patch_retained_30s_provider_event(provider) -> bool:
    from collections import deque

    from mide import gs379_webull_stream_data_truth as gs379
    from mide import gs470_30s_activation_truth as gs470
    from mide.market_data import EventType, MarketEvent

    owner = type(provider)
    current = getattr(owner, "_on_event", None)
    if not callable(current):
        return False
    if (
        getattr(current, "_gs379_tick_aggregation", False)
        or getattr(current, gs470._PROVIDER_EVENT_OWNER, False)
    ):
        if not callable(getattr(owner, "stream_30s_bars", None)):
            owner.stream_30s_bars = gs379._stream_30s_bars
        return False

    @wraps(current)
    def on_event(self, event: MarketEvent) -> None:
        ensure_production_30s_state(self)
        if event.type == EventType.TRADE:
            if event.symbol not in self._gs379_30s_closed:
                with self._lock:
                    self._gs379_30s_closed.setdefault(
                        event.symbol,
                        deque(
                            maxlen=gs470.THIRTY_SECOND_HISTORY
                        ),
                    )
            if not gs379._record_tick(self, event):
                return
            payload = dict(event.payload)
            payload["trade_size"] = payload.pop("volume", None)
            event = MarketEvent(
                event.provider,
                event.type,
                event.symbol,
                event.source_timestamp_ms,
                payload,
                event.sequence,
                event.wire_bytes,
            )
        current(self, event)

    on_event._gs379_tick_aggregation = True
    on_event._gs471_original = current
    setattr(on_event, gs470._PROVIDER_EVENT_OWNER, True)
    owner._on_event = on_event
    owner.stream_30s_bars = gs379._stream_30s_bars
    return True


def patch_retained_30s_sdk_stream(provider) -> bool:
    from mide import gs379_webull_stream_data_truth as gs379
    from mide import gs470_30s_activation_truth as gs470

    snapshot = getattr(provider, "_snapshot_client", None)
    sdk = getattr(snapshot, "sdk", None)
    data_client = getattr(sdk, "sdk_client", None)
    factory = getattr(
        data_client,
        "_walter_streaming_client_factory",
        None,
    )
    owner = type(sdk) if sdk is not None else None
    current = getattr(owner, "stream", None) if owner is not None else None
    if not callable(current) or not callable(factory):
        return False
    if (
        getattr(current, "_gs379_tick_transport", False)
        or getattr(current, gs470._SDK_STREAM_OWNER, False)
    ):
        return False

    @wraps(current)
    def stream(self, callback):
        active_factory = getattr(
            self.sdk_client,
            "_walter_streaming_client_factory",
            None,
        )
        if not callable(active_factory):
            raise RuntimeError(
                "Webull OpenAPI SDK lacks DataStreamingClient"
            )
        return gs379.OfficialWebullTickTransport(
            active_factory(),
            callback,
        )

    stream._gs379_tick_transport = True
    stream._gs471_original = current
    setattr(stream, gs470._SDK_STREAM_OWNER, True)
    owner.stream = stream
    return True


def production_30s_tick_age_seconds(provider) -> float | None:
    raw = live_30s_stream_diagnostics(provider).get(
        "last_tick_timestamp_ms"
    )
    try:
        stamp = int(raw)
    except (TypeError, ValueError):
        return None
    if stamp <= 0:
        return None
    now_ms = int(
        datetime.now(timezone.utc).timestamp() * 1000
    )
    return max(0.0, (now_ms - stamp) / 1000.0)


def retire_obsolete_30s_subscription(
    provider,
    *,
    force: bool = False,
) -> tuple[bool, str | None]:
    from mide import gs379_webull_stream_data_truth as gs379
    from mide import gs470_30s_activation_truth as gs470

    if getattr(provider, "_subscription", None) is None:
        return False, None
    age = production_30s_tick_age_seconds(provider)
    if force:
        reason = (
            "runtime 30s hook/activation changed; "
            "subscription callback must be rebound"
        )
    elif age is None:
        reason = (
            "subscribed Webull transport has no observed "
            "TICK heartbeat"
        )
    elif age > gs470.STALE_TICK_SECONDS:
        reason = f"last Webull TICK heartbeat is {age:.1f}s old"
    else:
        return False, None

    gs379._retire_provider_stream(provider)
    return True, reason


def activate_production_30s_evidence(provider) -> dict:
    from mide import gs379_webull_stream_data_truth as gs379
    from mide import gs470_30s_activation_truth as gs470

    production = production_30s_sdk_graph(provider)
    stream = live_30s_stream_diagnostics(provider)
    enabled_before = bool(
        getattr(provider, "_enable_streaming", False)
    ) if provider is not None else False
    state_rehydrated = enabled_now = rebound = False
    provider_event_patched = sdk_stream_patched = False
    retired = False
    retirement_reason = None

    if production:
        state_rehydrated = ensure_production_30s_state(provider)
        provider_event_patched = patch_retained_30s_provider_event(
            provider
        )
        sdk_stream_patched = patch_retained_30s_sdk_stream(provider)
        if not getattr(provider, "_enable_streaming", False):
            provider._enable_streaming = True
            enabled_now = True
            if getattr(provider, "_subscription", None) is None:
                stream["stream_connection_status"] = "disconnected"
                stream["stream_bypass_reason"] = None
        active_ref = getattr(gs379, "_ACTIVE_PROVIDER_REF", None)
        active = active_ref() if active_ref is not None else None
        if active is not provider:
            gs379._register_active_provider(provider)
            rebound = True
        retired, retirement_reason = (
            retire_obsolete_30s_subscription(
                provider,
                force=bool(
                    enabled_now
                    or provider_event_patched
                    or sdk_stream_patched
                ),
            )
        )
        gs470._remember_provider(provider)

    truth = {
        "authority": gs470.AUTHORITY,
        "production_sdk_graph": production,
        "streaming_enabled_before": enabled_before,
        "streaming_enabled_now": bool(
            getattr(provider, "_enable_streaming", False)
        ) if provider is not None else False,
        "activation_performed": enabled_now,
        "gs379_state_rehydrated": state_rehydrated,
        "active_provider_reasserted": rebound,
        "retained_provider_event_hook_patched": provider_event_patched,
        "retained_sdk_stream_hook_patched": sdk_stream_patched,
        "subscription_retired_for_rebind": retired,
        "subscription_retirement_reason": retirement_reason,
        "runtime_hard_bind": True,
        "genuine_webull_tick_only": True,
        "synthetic_30s_bars": False,
        "entry_authority_changed": False,
    }
    stream["gs470_30s_activation_truth"] = truth
    return dict(truth)


def safe_activate_production_30s(provider) -> dict:
    from mide import gs470_30s_activation_truth as gs470

    try:
        return gs470.activate_production_30s(provider)
    except Exception as exc:
        live_30s_stream_diagnostics(provider)[
            "gs471_runtime_hard_bind_error"
        ] = type(exc).__name__
        return {
            "authority": gs470.AUTHORITY,
            "production_sdk_graph": production_30s_sdk_graph(
                provider
            ),
            "runtime_hard_bind": True,
            "activation_error": type(exc).__name__,
            "genuine_webull_tick_only": True,
            "synthetic_30s_bars": False,
            "entry_authority_changed": False,
        }


def production_30s_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def production_30s_last_tick_age(
    last_tick_ms: Any,
) -> float | None:
    try:
        stamp = int(last_tick_ms)
    except (TypeError, ValueError):
        return None
    if stamp <= 0:
        return None
    now_ms = int(
        datetime.now(timezone.utc).timestamp() * 1000
    )
    return round(
        max(0.0, (now_ms - stamp) / 1000.0),
        1,
    )


def production_30s_stream_factory_present(provider) -> bool:
    snapshot = getattr(provider, "_snapshot_client", None)
    sdk = getattr(snapshot, "sdk", None)
    data_client = getattr(sdk, "sdk_client", None)
    return callable(
        getattr(
            data_client,
            "_walter_streaming_client_factory",
            None,
        )
    )


def production_30s_health(provider) -> dict:
    from mide import gs470_30s_activation_truth as gs470

    if provider is None:
        return {
            "authority": gs470.AUTHORITY,
            "provider_present": False,
            "production_sdk_graph": False,
            "streaming_enabled": False,
            "subscription_present": False,
            "subscribed_symbol_count": 0,
            "connection_status": "provider unavailable",
            "tick_messages_received": 0,
            "last_tick_timestamp_ms": None,
            "last_tick_age_seconds": None,
            "thirty_second_bars_closed": 0,
            "thirty_second_symbols_ready": 0,
            "stream_factory_present": False,
            "runtime_hard_bind": True,
            "genuine_webull_tick_only": True,
            "synthetic_30s_bars": False,
        }

    stream = live_30s_stream_diagnostics(provider)
    continuity = dict(
        stream.get("gs469_30s_stream_continuity") or {}
    )
    activation = dict(
        stream.get("gs470_30s_activation_truth") or {}
    )
    last_tick = stream.get("last_tick_timestamp_ms")
    provider_event = getattr(type(provider), "_on_event", None)
    snapshot = getattr(provider, "_snapshot_client", None)
    sdk = getattr(snapshot, "sdk", None)
    sdk_stream = (
        getattr(type(sdk), "stream", None)
        if sdk is not None
        else None
    )
    return {
        "authority": gs470.AUTHORITY,
        "provider_present": True,
        "production_sdk_graph": production_30s_sdk_graph(provider),
        "streaming_enabled": bool(
            getattr(provider, "_enable_streaming", False)
        ),
        "subscription_present": (
            getattr(provider, "_subscription", None) is not None
        ),
        "subscribed_symbol_count": len(
            set(getattr(provider, "_subscribed", set()) or set())
        ),
        "connection_status": str(
            stream.get("stream_connection_status") or "unknown"
        ),
        "tick_messages_received": production_30s_int(
            stream.get("tick_messages_received")
        ),
        "last_tick_timestamp_ms": (
            production_30s_int(last_tick, default=0) or None
        ),
        "last_tick_age_seconds": production_30s_last_tick_age(
            last_tick
        ),
        "thirty_second_bars_closed": production_30s_int(
            stream.get("thirty_second_bars_closed")
        ),
        "thirty_second_symbols_ready": production_30s_int(
            stream.get("thirty_second_symbols_ready")
        ),
        "stream_factory_present": (
            production_30s_stream_factory_present(provider)
        ),
        "provider_event_hook_present": bool(
            getattr(
                provider_event,
                "_gs379_tick_aggregation",
                False,
            )
            or getattr(
                provider_event,
                gs470._PROVIDER_EVENT_OWNER,
                False,
            )
        ),
        "sdk_tick_transport_hook_present": bool(
            getattr(
                sdk_stream,
                "_gs379_tick_transport",
                False,
            )
            or getattr(
                sdk_stream,
                gs470._SDK_STREAM_OWNER,
                False,
            )
        ),
        "gs469_restart_count": production_30s_int(
            stream.get("gs469_stale_stream_restarts")
        ),
        "gs469_restart_performed_last_check": bool(
            continuity.get("restart_performed")
        ),
        "gs469_restart_reason_last_check": continuity.get(
            "restart_reason"
        ),
        "gs470_activation_performed": bool(
            activation.get("activation_performed")
        ),
        "gs470_state_rehydrated": bool(
            activation.get("gs379_state_rehydrated")
        ),
        "gs471_subscription_retired_for_rebind": bool(
            activation.get("subscription_retired_for_rebind")
        ),
        "runtime_hard_bind": True,
        "genuine_webull_tick_only": True,
        "synthetic_30s_bars": False,
        "entry_authority_changed": False,
    }


def active_or_last_30s_provider():
    from mide import gs379_webull_stream_data_truth as gs379
    from mide import gs470_30s_activation_truth as gs470

    reference = getattr(gs379, "_ACTIVE_PROVIDER_REF", None)
    if reference is not None:
        try:
            provider = reference()
        except TypeError:
            provider = None
        if provider is not None:
            return provider
    return gs470._last_provider()


def install_production_30s_activation_boundary() -> None:
    from mide import gs470_30s_activation_truth as gs470
    from mide import webull_live

    current = webull_live.LiveWebullProvider.initialize_quotes
    if getattr(current, gs470._INIT_OWNER, False):
        return

    @wraps(current)
    def initialize_quotes(self, symbols, *args, **kwargs):
        gs470._safe_activate(self)
        return current(self, symbols, *args, **kwargs)

    initialize_quotes._gs470_30s_activation_truth = True
    initialize_quotes._gs470_original = current
    setattr(initialize_quotes, gs470._INIT_OWNER, True)
    webull_live.LiveWebullProvider.initialize_quotes = (
        initialize_quotes
    )


def bind_production_30s_context_class(context) -> bool:
    from mide import gs470_30s_activation_truth as gs470

    if context is None:
        return False
    owner = type(context)
    current = getattr(owner, "__setattr__", None)
    if (
        not callable(current)
        or getattr(
            current,
            gs470._CONTEXT_SETATTR_OWNER,
            False,
        )
    ):
        return False

    @wraps(current)
    def context_setattr(self, name, value):
        current(self, name, value)
        if name == "provider_instance" and value is not None:
            gs470._safe_activate(value)

    context_setattr._gs471_original = current
    setattr(
        context_setattr,
        gs470._CONTEXT_SETATTR_OWNER,
        True,
    )
    try:
        owner.__setattr__ = context_setattr
    except (AttributeError, TypeError):
        return False
    return True


def install_production_30s_scan_context_hard_bind() -> None:
    from mide import completed_scan
    from mide import gs470_30s_activation_truth as gs470

    current = completed_scan.scan_context
    if getattr(current, gs470._SCAN_CONTEXT_OWNER, False):
        return

    @wraps(current)
    def scan_context(state):
        context = current(state)
        gs470._bind_context_class(context)
        provider = getattr(context, "provider_instance", None)
        if provider is not None:
            gs470._safe_activate(provider)
        return context

    scan_context._gs471_original = current
    setattr(
        scan_context,
        gs470._SCAN_CONTEXT_OWNER,
        True,
    )
    completed_scan.scan_context = scan_context


def install_production_30s_market_evidence() -> None:
    install_production_30s_activation_boundary()
    install_production_30s_scan_context_hard_bind()



# ---------------------------------------------------------------------------
# GS475/GS476 session-aware Webull snapshot source-price truth
# ---------------------------------------------------------------------------

def snapshot_truth_number(value):
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def snapshot_session_price_fields(
    now_et: datetime,
) -> tuple[str, str, str] | None:
    from mide import gs475_premarket_snapshot_truth as gs475

    if now_et.tzinfo is None:
        now_et = now_et.replace(tzinfo=gs475.EASTERN)
    else:
        now_et = now_et.astimezone(gs475.EASTERN)
    clock = now_et.time().replace(tzinfo=None)
    if time(4, 0) <= clock < time(9, 30):
        return ("ext_price", "ext_trade_time", "PRE")
    if time(16, 0) <= clock < time(20, 0):
        return ("ext_price", "ext_trade_time", "ATH")
    return None


def overlay_snapshot_session_price(
    row: dict,
    now_et: datetime,
) -> dict:
    from mide import gs475_premarket_snapshot_truth as gs475

    fields = gs475._session_price_fields(now_et)
    if fields is None:
        return row
    price_field, trade_time_field, session = fields
    session_price = snapshot_truth_number(
        row.get(price_field)
    )
    if session_price is None or session_price <= 0:
        return row
    updated = dict(row)
    updated["_walter_regular_session_price"] = row.get(
        "price"
    )
    updated["price"] = row.get(price_field)
    session_trade_time = row.get(trade_time_field)
    if session_trade_time not in (None, ""):
        updated["last_trade_time"] = session_trade_time
    updated["_walter_snapshot_price_source"] = price_field
    updated["_walter_snapshot_session"] = session
    return updated


def apply_snapshot_session_truth(
    payload,
    *,
    now_et: datetime | None = None,
):
    from mide import gs475_premarket_snapshot_truth as gs475

    now_et = now_et or gs475._now_eastern()
    if isinstance(payload, list):
        return [
            apply_snapshot_session_truth(
                item,
                now_et=now_et,
            )
            for item in payload
        ]
    if isinstance(payload, tuple):
        return tuple(
            apply_snapshot_session_truth(
                item,
                now_et=now_et,
            )
            for item in payload
        )
    if not isinstance(payload, dict):
        return payload

    updated = {
        key: apply_snapshot_session_truth(
            value,
            now_et=now_et,
        )
        for key, value in payload.items()
    }
    symbol = (
        updated.get("symbol")
        or updated.get("ticker")
        or updated.get("ticker_symbol")
    )
    if symbol:
        return overlay_snapshot_session_price(
            updated,
            now_et,
        )
    return updated


def extended_snapshot_without_overnight(
    client,
    symbols,
):
    from mide import webull_sdk

    symbols = list(symbols)
    if len(symbols) > webull_sdk.MAX_SNAPSHOT_SYMBOLS:
        raise ValueError(
            "Webull snapshot requests are limited to 100 symbols"
        )
    method = client._operation(
        ("get_snapshot", "get_stock_snapshot")
    )
    response = method(
        symbols=",".join(symbols),
        category="US_STOCK",
        extend_hour_required=True,
    )
    client._capture_first_snapshot_response(response)
    return webull_sdk._plain(response)


def inherit_snapshot_truth_wrapper(
    wrapper,
    wrapped,
) -> None:
    for name, value in getattr(
        wrapped,
        "__dict__",
        {},
    ).items():
        if (
            name.startswith("_gs")
            and not hasattr(wrapper, name)
        ):
            setattr(wrapper, name, value)


def install_snapshot_session_truth() -> None:
    from mide import gs475_premarket_snapshot_truth as gs475
    from mide import webull_sdk

    current = webull_sdk.WebullSDKClient.stock_snapshot
    if getattr(current, gs475.OWNER_ATTR, False):
        return

    base = getattr(current, "_gs475_original", current)

    def stock_snapshot_with_session_truth(
        self,
        symbols,
        *,
        extended_hours: bool = False,
    ):
        now_et = gs475._now_eastern()
        fields = gs475._session_price_fields(now_et)
        request_extended = fields is not None

        if request_extended:
            payload = (
                gs475._extended_snapshot_without_overnight(
                    self,
                    symbols,
                )
            )
        else:
            payload = base(
                self,
                symbols,
                extended_hours=False,
            )

        result = gs475.apply_snapshot_session_truth(
            payload,
            now_et=now_et,
        )
        self.last_snapshot_extended_requested = (
            request_extended
        )
        self.last_snapshot_overnight_requested = False
        self.last_snapshot_session_price_field = (
            fields[0] if fields else "price"
        )
        return result

    inherit_snapshot_truth_wrapper(
        stock_snapshot_with_session_truth,
        current,
    )
    stock_snapshot_with_session_truth._gs475_premarket_snapshot_truth = True
    stock_snapshot_with_session_truth._gs476_night_entitlement_safe = True
    stock_snapshot_with_session_truth._gs475_original = base
    setattr(
        stock_snapshot_with_session_truth,
        gs475.OWNER_ATTR,
        True,
    )
    webull_sdk.WebullSDKClient.stock_snapshot = (
        stock_snapshot_with_session_truth
    )



# ---------------------------------------------------------------------------
# GS488 Webull rc105 connection-limit containment
# ---------------------------------------------------------------------------

WEBULL_CONNECTION_LIMIT_AUTHORITY = (
    "WEBULL_CONNECTION_LIMIT_CONTAINMENT"
)
WEBULL_CONNECTION_LIMIT_COOLDOWN_SECONDS = 300.0
WEBULL_CONNECTION_LIMIT_BACKOFF_SECONDS = (
    300.0,
    600.0,
    900.0,
)


def connection_limit_stream(provider) -> dict:
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


def connection_limit_rejection(value: Any) -> bool:
    text = " ".join(
        str(value or "").split()
    ).casefold()
    return (
        "connection limit exceeded" in text
        or (
            "rc code: 105" in text
            and "limit" in text
        )
    )


def connection_limit_cooldown(
    failures: Any,
) -> float:
    from mide import gs488_webull_connection_limit_backoff as gs488

    try:
        count = max(1, int(failures))
    except (TypeError, ValueError):
        count = 1
    return gs488.BACKOFF_SECONDS[
        min(count - 1, len(gs488.BACKOFF_SECONDS) - 1)
    ]


def connection_limit_state(provider) -> dict:
    from mide import gs488_webull_connection_limit_backoff as gs488

    stream = gs488._stream(provider)
    state = stream.get(
        "gs488_connection_limit_backoff"
    )
    if not isinstance(state, dict):
        state = {
            "authority": gs488.AUTHORITY,
            "active": False,
            "cooldown_seconds": gs488.COOLDOWN_SECONDS,
            "backoff_schedule_seconds": list(
                gs488.BACKOFF_SECONDS
            ),
            "gs489_graduated_backoff": True,
            "next_retry_epoch": None,
            "consecutive_limit_failures": 0,
            "suppressed_attempts": 0,
            "last_limit_failure": None,
            "rest_snapshot_history_unchanged": True,
            "genuine_webull_tick_only": True,
            "trading_authority_changed": False,
        }
        stream[
            "gs488_connection_limit_backoff"
        ] = state
    return state


def refresh_connection_limit_deadline(
    provider,
    *,
    now: float,
) -> dict:
    from mide import gs488_webull_connection_limit_backoff as gs488

    state = gs488._state(provider)
    if (
        not state.get("active")
        or getattr(
            provider,
            "_subscription",
            None,
        )
        is not None
    ):
        return state
    failures = int(
        state.get(
            "consecutive_limit_failures",
            0,
        )
        or 0
    )
    if failures <= 0:
        return state
    cooldown = gs488._cooldown_for_failures(
        failures
    )
    try:
        last_failure = float(
            state.get("last_limit_failure_epoch")
        )
    except (TypeError, ValueError):
        last_failure = now
    desired_deadline = last_failure + cooldown
    try:
        current_deadline = float(
            state.get("next_retry_epoch")
        )
    except (TypeError, ValueError):
        current_deadline = 0.0
    state["cooldown_seconds"] = cooldown
    if desired_deadline > current_deadline:
        state["next_retry_epoch"] = (
            desired_deadline
        )
        state[
            "gs489_retained_deadline_extended"
        ] = True
    state["gs489_graduated_backoff"] = True
    return state


def connection_limit_backoff_snapshot(
    provider,
    *,
    now: float | None = None,
) -> dict:
    from mide import gs488_webull_connection_limit_backoff as gs488

    if provider is None:
        return {
            "authority": gs488.AUTHORITY,
            "provider_present": False,
            "active": False,
            "cooldown_seconds": gs488.COOLDOWN_SECONDS,
            "backoff_schedule_seconds": list(
                gs488.BACKOFF_SECONDS
            ),
            "gs489_graduated_backoff": True,
            "next_retry_epoch": None,
            "seconds_remaining": None,
            "consecutive_limit_failures": 0,
            "suppressed_attempts": 0,
            "rest_snapshot_history_unchanged": True,
            "trading_authority_changed": False,
        }
    current = float(
        epoch_time() if now is None else now
    )
    state = dict(
        gs488._refresh_active_deadline(
            provider,
            now=current,
        )
    )
    deadline = state.get("next_retry_epoch")
    try:
        remaining = (
            max(
                0.0,
                float(deadline) - current,
            )
            if deadline is not None
            else 0.0
        )
    except (TypeError, ValueError):
        remaining = 0.0
    active = bool(
        getattr(
            provider,
            "_subscription",
            None,
        )
        is None
        and remaining > 0.0
        and state.get("active")
    )
    state.update(
        provider_present=True,
        active=active,
        seconds_remaining=(
            round(remaining, 1)
            if active
            else 0.0
        ),
    )
    return state


def ensure_stream_with_backoff(
    original: Callable,
    provider,
    symbols,
    *,
    now: float | None = None,
):
    from mide import gs488_webull_connection_limit_backoff as gs488

    current = float(
        epoch_time() if now is None else now
    )
    state = gs488._refresh_active_deadline(
        provider,
        now=current,
    )

    if (
        getattr(
            provider,
            "_subscription",
            None,
        )
        is not None
    ):
        result = original(symbols)
        if result:
            state["active"] = False
            state["next_retry_epoch"] = None
            state[
                "consecutive_limit_failures"
            ] = 0
            state["cooldown_seconds"] = (
                gs488.COOLDOWN_SECONDS
            )
        return result

    deadline = state.get("next_retry_epoch")
    try:
        remaining = (
            float(deadline) - current
            if deadline is not None
            else 0.0
        )
    except (TypeError, ValueError):
        remaining = 0.0
    if (
        bool(state.get("active"))
        and remaining > 0.0
    ):
        state["suppressed_attempts"] = int(
            state.get(
                "suppressed_attempts",
                0,
            )
            or 0
        ) + 1
        state[
            "last_suppressed_epoch"
        ] = current
        return False

    stream = gs488._stream(provider)
    failures_before = len(
        list(
            stream.get(
                "subscription_failures"
            )
            or []
        )
    )
    result = original(symbols)
    failures = list(
        stream.get("subscription_failures")
        or []
    )
    newest = (
        failures[-1]
        if len(failures) > failures_before
        else None
    )

    if result:
        state["active"] = False
        state["next_retry_epoch"] = None
        state[
            "consecutive_limit_failures"
        ] = 0
        state["cooldown_seconds"] = (
            gs488.COOLDOWN_SECONDS
        )
        state[
            "last_recovery_epoch"
        ] = current
        return result

    if gs488._is_connection_limit(newest):
        state["active"] = True
        failures_count = int(
            state.get(
                "consecutive_limit_failures",
                0,
            )
            or 0
        ) + 1
        cooldown = gs488._cooldown_for_failures(
            failures_count
        )
        state["cooldown_seconds"] = cooldown
        state[
            "backoff_schedule_seconds"
        ] = list(gs488.BACKOFF_SECONDS)
        state[
            "gs489_graduated_backoff"
        ] = True
        state[
            "next_retry_epoch"
        ] = current + cooldown
        state[
            "consecutive_limit_failures"
        ] = failures_count
        state[
            "last_limit_failure"
        ] = "WEBULL_RC105_CONNECTION_LIMIT"
        state[
            "last_limit_failure_epoch"
        ] = current
    else:
        state["active"] = False
        state["next_retry_epoch"] = None
    return result


def upgrade_connection_limit_wrapper_global(
    function,
    name: str,
    value: Any,
) -> bool:
    globals_dict = getattr(
        function,
        "__globals__",
        None,
    )
    if (
        not isinstance(globals_dict, dict)
        or name not in globals_dict
    ):
        return False
    globals_dict[name] = value
    return True


def install_for_provider(provider) -> bool:
    from mide import gs488_webull_connection_limit_backoff as gs488

    if provider is None:
        return False
    current = getattr(
        provider,
        "ensure_stream",
        None,
    )
    if not callable(current):
        return False
    function = getattr(
        current,
        "__func__",
        current,
    )
    marker = (
        getattr(
            function,
            gs488._OWNER,
            None,
        )
        or getattr(
            current,
            gs488._PROVIDER_OWNER,
            None,
        )
    )
    if marker == gs488.REVISION:
        gs488._refresh_active_deadline(
            provider,
            now=epoch_time(),
        )
        return False
    if marker:
        if not gs488._upgrade_wrapper_global(
            function,
            "ensure_stream_with_backoff",
            ensure_stream_with_backoff,
        ):
            return False
        setattr(
            function,
            gs488._OWNER,
            gs488.REVISION,
        )
        setattr(
            function,
            gs488._PROVIDER_OWNER,
            gs488.REVISION,
        )
        gs488._refresh_active_deadline(
            provider,
            now=epoch_time(),
        )
        return True

    @wraps(current)
    def guarded(symbols):
        return ensure_stream_with_backoff(
            current,
            provider,
            symbols,
        )

    setattr(
        guarded,
        gs488._OWNER,
        gs488.REVISION,
    )
    setattr(
        guarded,
        gs488._PROVIDER_OWNER,
        gs488.REVISION,
    )
    guarded._gs488_original = current
    try:
        provider.ensure_stream = guarded
    except (AttributeError, TypeError):
        return False
    gs488._state(provider)
    return True


def install_connection_limit_clean_class() -> None:
    from mide import gs488_webull_connection_limit_backoff as gs488
    from mide import webull_live

    current = (
        webull_live.LiveWebullProvider.ensure_stream
    )
    marker = getattr(
        current,
        gs488._OWNER,
        None,
    )
    if marker == gs488.REVISION:
        return
    if marker:
        if gs488._upgrade_wrapper_global(
            current,
            "ensure_stream_with_backoff",
            ensure_stream_with_backoff,
        ):
            setattr(
                current,
                gs488._OWNER,
                gs488.REVISION,
            )
        return

    @wraps(current)
    def ensure_stream(self, symbols):
        return ensure_stream_with_backoff(
            lambda active_symbols: current(
                self,
                active_symbols,
            ),
            self,
            symbols,
        )

    setattr(
        ensure_stream,
        gs488._OWNER,
        gs488.REVISION,
    )
    ensure_stream._gs488_original = current
    webull_live.LiveWebullProvider.ensure_stream = (
        ensure_stream
    )


def install_connection_limit_activation_bind() -> None:
    from mide import gs470_30s_activation_truth as gs470
    from mide import gs488_webull_connection_limit_backoff as gs488

    current = gs470._safe_activate
    marker = getattr(
        current,
        gs488._GS470_OWNER,
        None,
    )
    if marker == gs488.REVISION:
        return
    if marker:
        if gs488._upgrade_wrapper_global(
            current,
            "install_for_provider",
            install_for_provider,
        ):
            setattr(
                current,
                gs488._GS470_OWNER,
                gs488.REVISION,
            )
        return

    @wraps(current)
    def safe_activate(provider):
        install_for_provider(provider)
        return current(provider)

    setattr(
        safe_activate,
        gs488._GS470_OWNER,
        gs488.REVISION,
    )
    safe_activate._gs488_original = current
    gs470._safe_activate = safe_activate


def install_connection_limit_recorder_bind() -> None:
    from mide import gs427_flight_recorder_latency_hard_bind as gs427
    from mide import gs487_cached_recorder_instance_bind as gs487
    from mide import gs488_webull_connection_limit_backoff as gs488

    current = gs487.install_for_recorder
    marker = getattr(
        current,
        gs488._GS487_OWNER,
        None,
    )
    if marker == gs488.REVISION:
        return
    if marker:
        if gs488._upgrade_wrapper_global(
            current,
            "install_for_provider",
            install_for_provider,
        ):
            setattr(
                current,
                gs488._GS487_OWNER,
                gs488.REVISION,
            )
        return

    @wraps(current)
    def install_for_recorder(recorder):
        provider, _provider_source = (
            gs427._active_provider()
        )
        install_for_provider(provider)
        return current(recorder)

    setattr(
        install_for_recorder,
        gs488._GS487_OWNER,
        gs488.REVISION,
    )
    install_for_recorder._gs488_original = (
        current
    )
    gs487.install_for_recorder = (
        install_for_recorder
    )


def install_connection_limit_market_evidence() -> None:
    install_connection_limit_clean_class()
    install_connection_limit_activation_bind()
    install_connection_limit_recorder_bind()



# ---------------------------------------------------------------------------
# GS489 graduated Webull rc105 backoff
# ---------------------------------------------------------------------------

GRADUATED_BACKOFF_AUTHORITY = (
    "WEBULL_CONNECTION_LIMIT_GRADUATED_BACKOFF"
)
GRADUATED_BACKOFF_SECONDS = (
    300.0,
    600.0,
    900.0,
)


def graduated_backoff_state(provider) -> dict:
    from mide import gs489_webull_graduated_backoff as gs489

    stream = connection_limit_stream(provider)
    state = stream.get(gs489._STATE_KEY)
    if not isinstance(state, dict):
        state = {
            "authority": WEBULL_CONNECTION_LIMIT_AUTHORITY,
            "active": False,
            "cooldown_seconds": gs489.BACKOFF_SECONDS[0],
            "next_retry_epoch": None,
            "consecutive_limit_failures": 0,
            "suppressed_attempts": 0,
            "last_limit_failure": None,
            "rest_snapshot_history_unchanged": True,
            "genuine_webull_tick_only": True,
            "trading_authority_changed": False,
        }
        stream[gs489._STATE_KEY] = state
    state["backoff_schedule_seconds"] = list(
        gs489.BACKOFF_SECONDS
    )
    state["gs489_graduated_backoff"] = True
    state["gs489_authority"] = gs489.AUTHORITY
    return state


def graduated_connection_limit_rejection(
    value: Any,
) -> bool:
    return connection_limit_rejection(value)


def graduated_backoff_cooldown(
    value: Any,
) -> float:
    from mide import gs489_webull_graduated_backoff as gs489

    try:
        failures = max(1, int(value))
    except (TypeError, ValueError):
        failures = 1
    return gs489.BACKOFF_SECONDS[
        min(
            failures - 1,
            len(gs489.BACKOFF_SECONDS) - 1,
        )
    ]


def refresh_graduated_backoff_deadline(
    provider,
    *,
    now: float,
) -> dict:
    from mide import gs489_webull_graduated_backoff as gs489

    state = gs489._state(provider)
    if (
        not state.get("active")
        or getattr(provider, "_subscription", None) is not None
    ):
        return state
    try:
        failures = int(
            state.get(
                "consecutive_limit_failures",
                0,
            )
            or 0
        )
    except (TypeError, ValueError):
        failures = 0
    if failures <= 0:
        return state
    cooldown = gs489._cooldown_for_failures(
        failures
    )
    try:
        last_failure = float(
            state.get("last_limit_failure_epoch")
        )
    except (TypeError, ValueError):
        last_failure = now
    desired_deadline = last_failure + cooldown
    try:
        current_deadline = float(
            state.get("next_retry_epoch")
        )
    except (TypeError, ValueError):
        current_deadline = 0.0
    state["cooldown_seconds"] = cooldown
    if desired_deadline > current_deadline:
        state["next_retry_epoch"] = (
            desired_deadline
        )
        state[
            "gs489_retained_deadline_extended"
        ] = True
    return state


def ensure_stream_with_graduated_backoff(
    original: Callable,
    provider,
    symbols,
    *,
    now: float | None = None,
):
    from mide import gs489_webull_graduated_backoff as gs489

    current = float(
        gs489.time.time()
        if now is None
        else now
    )
    state = gs489._refresh_active_deadline(
        provider,
        now=current,
    )

    if getattr(provider, "_subscription", None) is not None:
        result = original(symbols)
        if result:
            state["active"] = False
            state["next_retry_epoch"] = None
            state[
                "consecutive_limit_failures"
            ] = 0
            state["cooldown_seconds"] = (
                gs489.BACKOFF_SECONDS[0]
            )
            state[
                "last_recovery_epoch"
            ] = current
        return result

    try:
        deadline = float(
            state.get("next_retry_epoch")
        )
    except (TypeError, ValueError):
        deadline = 0.0
    if state.get("active") and deadline > current:
        state["suppressed_attempts"] = int(
            state.get(
                "suppressed_attempts",
                0,
            )
            or 0
        ) + 1
        state[
            "last_suppressed_epoch"
        ] = current
        return False

    stream = gs489._stream(provider)
    before = len(
        list(
            stream.get(
                "subscription_failures"
            )
            or []
        )
    )
    result = original(symbols)
    failures = list(
        stream.get("subscription_failures")
        or []
    )
    newest = (
        failures[-1]
        if len(failures) > before
        else None
    )

    if result:
        state["active"] = False
        state["next_retry_epoch"] = None
        state[
            "consecutive_limit_failures"
        ] = 0
        state["cooldown_seconds"] = (
            gs489.BACKOFF_SECONDS[0]
        )
        state[
            "last_recovery_epoch"
        ] = current
        return result

    if gs489._is_connection_limit(newest):
        count = int(
            state.get(
                "consecutive_limit_failures",
                0,
            )
            or 0
        ) + 1
        cooldown = gs489._cooldown_for_failures(
            count
        )
        state["active"] = True
        state["cooldown_seconds"] = cooldown
        state[
            "next_retry_epoch"
        ] = current + cooldown
        state[
            "consecutive_limit_failures"
        ] = count
        state[
            "last_limit_failure"
        ] = "WEBULL_RC105_CONNECTION_LIMIT"
        state[
            "last_limit_failure_epoch"
        ] = current
    else:
        state["active"] = False
        state["next_retry_epoch"] = None
    return result


def install_graduated_backoff_for_provider(
    provider,
) -> bool:
    from mide import gs489_webull_graduated_backoff as gs489

    if provider is None:
        return False
    current = getattr(
        provider,
        "ensure_stream",
        None,
    )
    if not callable(current):
        return False
    function = getattr(
        current,
        "__func__",
        current,
    )

    if (
        getattr(
            function,
            gs489._GS489_OWNER,
            None,
        )
        == gs489.REVISION
    ):
        gs489._refresh_active_deadline(
            provider,
            now=gs489.time.time(),
        )
        return False

    if getattr(
        function,
        gs489._GS488_OWNER,
        False,
    ):
        globals_dict = getattr(
            function,
            "__globals__",
            None,
        )
        if (
            not isinstance(globals_dict, dict)
            or "ensure_stream_with_backoff"
            not in globals_dict
        ):
            return False
        globals_dict[
            "ensure_stream_with_backoff"
        ] = ensure_stream_with_graduated_backoff
        setattr(
            function,
            gs489._GS489_OWNER,
            gs489.REVISION,
        )
        gs489._refresh_active_deadline(
            provider,
            now=gs489.time.time(),
        )
        return True

    @wraps(current)
    def guarded(symbols):
        return ensure_stream_with_graduated_backoff(
            current,
            provider,
            symbols,
        )

    setattr(
        guarded,
        gs489._GS489_OWNER,
        gs489.REVISION,
    )
    guarded._gs489_original = current
    try:
        provider.ensure_stream = guarded
    except (AttributeError, TypeError):
        return False
    gs489._refresh_active_deadline(
        provider,
        now=gs489.time.time(),
    )
    return True



# ---------------------------------------------------------------------------
# GS490 Webull TICK initiation window
# ---------------------------------------------------------------------------

WEBULL_TICK_WINDOW_AUTHORITY = (
    "WEBULL_TICK_INITIATION_WINDOW"
)
WEBULL_TICK_STREAM_START_ET = time(4, 0)
WEBULL_TICK_STREAM_END_ET = time(20, 0)


def webull_tick_window_utc(
    value: datetime | None = None,
) -> datetime:
    if value is None:
        return datetime.now(timezone.utc)
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def webull_tick_stream_window_open(
    value: datetime | None = None,
) -> bool:
    from mide import gs490_webull_stream_window_guard as gs490
    from mide.time_service import eastern_time

    current = eastern_time(gs490._utc(value))
    clock = current.time().replace(tzinfo=None)
    return (
        current.weekday() < 5
        and gs490.STREAM_START_ET
        <= clock
        < gs490.STREAM_END_ET
    )


def webull_tick_window_stream(provider) -> dict:
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


def ensure_stream_in_window(
    original: Callable,
    provider,
    symbols,
    *,
    now: datetime | None = None,
):
    from mide import gs490_webull_stream_window_guard as gs490

    stream = gs490._stream(provider)
    existing = (
        getattr(provider, "_subscription", None)
        is not None
    )
    allowed = gs490.stream_window_open(now)
    state = stream.get(
        "gs490_stream_window_guard"
    )
    if not isinstance(state, dict):
        state = {
            "authority": gs490.AUTHORITY,
            "blocked_new_connection_attempts": 0,
            "trading_authority_changed": False,
            "rest_snapshot_history_unchanged": True,
            "genuine_webull_tick_only": True,
        }
        stream[
            "gs490_stream_window_guard"
        ] = state
    state.update(
        window_open=allowed,
        subscription_present=existing,
        stream_start_et="04:00",
        stream_end_et="20:00",
        weekdays_only=True,
    )

    if not existing and not allowed:
        state[
            "blocked_new_connection_attempts"
        ] = int(
            state.get(
                "blocked_new_connection_attempts",
                0,
            )
            or 0
        ) + 1
        state["blocked_last_check"] = True
        stream[
            "stream_connection_status"
        ] = "bypassed"
        stream[
            "stream_bypass_reason"
        ] = gs490.BYPASS_REASON
        return False

    state["blocked_last_check"] = False
    if (
        stream.get("stream_bypass_reason")
        == gs490.BYPASS_REASON
    ):
        stream["stream_bypass_reason"] = None
        if (
            stream.get(
                "stream_connection_status"
            )
            == "bypassed"
        ):
            stream[
                "stream_connection_status"
            ] = "disconnected"
    return original(symbols)


def install_stream_window_for_provider(
    provider,
) -> bool:
    from mide import gs490_webull_stream_window_guard as gs490

    if provider is None:
        return False
    current = getattr(
        provider,
        "ensure_stream",
        None,
    )
    if not callable(current):
        return False
    function = getattr(
        current,
        "__func__",
        current,
    )
    if (
        getattr(
            function,
            gs490._OWNER,
            None,
        )
        == gs490.REVISION
        or getattr(
            current,
            gs490._OWNER,
            None,
        )
        == gs490.REVISION
    ):
        return False

    @wraps(current)
    def guarded(symbols):
        return ensure_stream_in_window(
            current,
            provider,
            symbols,
        )

    setattr(
        guarded,
        gs490._OWNER,
        gs490.REVISION,
    )
    guarded._gs490_original = current
    try:
        provider.ensure_stream = guarded
    except (AttributeError, TypeError):
        return False
    return True



# ---------------------------------------------------------------------------
# GS494 bounded partial Webull snapshot recovery
# ---------------------------------------------------------------------------

PARTIAL_SNAPSHOT_AUTHORITY = (
    "WEBULL_OFFICIAL_SNAPSHOT_PARTIAL_RETRY"
)


def partial_snapshot_symbols(
    values: Iterable[str],
) -> list[str]:
    return list(
        dict.fromkeys(
            str(value or "").strip().upper()
            for value in values or []
            if str(value or "").strip()
        )
    )


def initialize_quotes_with_partial_retry(
    original: Callable,
    provider,
    symbols: Iterable[str],
    *,
    batch_size: int,
):
    from mide import gs494_partial_snapshot_recovery as gs494
    from mide.webull_live import webull_snapshot_symbol_supported

    submitted = gs494._symbols(symbols)
    wanted = [
        symbol
        for symbol in submitted
        if webull_snapshot_symbol_supported(symbol)
    ]

    first = original(
        submitted,
        batch_size=batch_size,
    )
    if not isinstance(first, dict):
        return first

    missing = [
        symbol
        for symbol in wanted
        if symbol not in first
    ]
    diagnostics = getattr(
        provider,
        "diagnostics",
        None,
    )
    if not isinstance(diagnostics, dict):
        diagnostics = {}
        try:
            provider.diagnostics = diagnostics
        except Exception:
            pass
    stream = diagnostics.setdefault(
        "webull_stream",
        {},
    )
    trace = {
        "authority": PARTIAL_SNAPSHOT_AUTHORITY,
        "requested_symbols": len(wanted),
        "first_pass_returned": len(
            [
                symbol
                for symbol in wanted
                if symbol in first
            ]
        ),
        "retry_attempted": bool(missing),
        "retry_requested": len(missing),
        "retry_recovered": 0,
        "unresolved_count": len(missing),
        "unresolved_symbols": list(missing),
        "extra_provider_requests_max": (
            1 if missing else 0
        ),
        "stale_price_substitution": False,
        "trading_authority_changed": False,
    }
    stream[
        "snapshot_partial_retry"
    ] = trace

    if not missing:
        return first

    previous_discovered = stream.get(
        "discovered_symbols"
    )
    try:
        retry = original(
            missing,
            batch_size=min(
                max(1, int(batch_size)),
                len(missing),
            ),
        )
    except Exception as exc:
        trace[
            "retry_error_type"
        ] = type(exc).__name__
        trace[
            "unresolved_count"
        ] = len(missing)
        trace[
            "unresolved_symbols"
        ] = list(missing)
        if previous_discovered is not None:
            stream[
                "discovered_symbols"
            ] = previous_discovered
        return first
    finally:
        if previous_discovered is not None:
            stream[
                "discovered_symbols"
            ] = previous_discovered

    retry = (
        retry
        if isinstance(retry, dict)
        else {}
    )
    recovered = {
        symbol: retry[symbol]
        for symbol in missing
        if symbol in retry
    }
    combined = dict(first)
    combined.update(recovered)
    unresolved = [
        symbol
        for symbol in missing
        if symbol not in recovered
    ]
    trace.update(
        retry_recovered=len(recovered),
        unresolved_count=len(unresolved),
        unresolved_symbols=unresolved,
    )
    return combined


def install_partial_snapshot_recovery_for_provider(
    provider,
) -> bool:
    from mide import gs494_partial_snapshot_recovery as gs494

    if provider is None:
        return False
    current = getattr(
        provider,
        "initialize_quotes",
        None,
    )
    if not callable(current):
        return False
    function = getattr(
        current,
        "__func__",
        current,
    )
    if (
        getattr(
            function,
            gs494._OWNER,
            None,
        )
        == gs494.REVISION
        or getattr(
            current,
            gs494._OWNER,
            None,
        )
        == gs494.REVISION
    ):
        return False

    @wraps(current)
    def initialize_quotes(
        symbols,
        *,
        batch_size=100,
    ):
        return gs494.initialize_quotes_with_partial_retry(
            current,
            provider,
            symbols,
            batch_size=batch_size,
        )

    setattr(
        initialize_quotes,
        gs494._OWNER,
        gs494.REVISION,
    )
    initialize_quotes._gs494_original = current
    try:
        provider.initialize_quotes = (
            initialize_quotes
        )
    except (AttributeError, TypeError):
        return False
    return True


__all__ = [
    "reset_retest_number",
    "reset_retest_one_minute",
    "reset_retest_current_webull_radar_attention",
    "reset_retest_fresh_source",
    "reset_retest_attention_evidence",
    "reset_retest_eligible",
    "canonical_30s_progression_rung",
    "install_canonical_30s_progression_rung",
    "canonical_30s_primary_above_vwap",
    "canonicalize_gs397_with_30s_vwap",
    "install_canonical_30s_gs397_propagation",
    "canonical_30s_empty_alignment",
    "canonical_30s_alignment_truth",
    "canonical_alignment_summary_with_30s_truth",
    "install_canonical_30s_alignment_truth",
    "maturation_finite",
    "maturation_line_cross_event",
    "maturation_confirmation_details_with_line_cross",
    "maturation_timeframe_event_with_line_cross",
    "install_maturation_line_cross_enrichment",
    "progression_number",
    "progression_timestamp",
    "thirty_second_progression_rung",
    "progression_rung_event",
    "progression_halted",
    "progression_current_attention",
    "progression_supporting_flow",
    "crossover_progression",
    "progression_signal",
    "install_partial_snapshot_recovery_for_provider",
    "initialize_quotes_with_partial_retry",
    "partial_snapshot_symbols",
    "install_stream_window_for_provider",
    "ensure_stream_in_window",
    "webull_tick_window_stream",
    "webull_tick_stream_window_open",
    "webull_tick_window_utc",
    "install_graduated_backoff_for_provider",
    "ensure_stream_with_graduated_backoff",
    "refresh_graduated_backoff_deadline",
    "graduated_backoff_cooldown",
    "graduated_connection_limit_rejection",
    "graduated_backoff_state",
    "install_connection_limit_market_evidence",
    "install_connection_limit_clean_class",
    "install_connection_limit_activation_bind",
    "install_connection_limit_recorder_bind",
    "install_for_provider",
    "upgrade_connection_limit_wrapper_global",
    "ensure_stream_with_backoff",
    "connection_limit_backoff_snapshot",
    "refresh_connection_limit_deadline",
    "connection_limit_state",
    "connection_limit_cooldown",
    "connection_limit_rejection",
    "connection_limit_stream",
    "install_snapshot_session_truth",
    "extended_snapshot_without_overnight",
    "apply_snapshot_session_truth",
    "overlay_snapshot_session_price",
    "snapshot_session_price_fields",
    "install_live_30s_stream_continuity",
    "ensure_live_30s_stream_continuity",
    "reassert_active_30s_provider",
    "active_30s_registry_provider",
    "install_production_30s_market_evidence",
    "install_production_30s_activation_boundary",
    "install_production_30s_scan_context_hard_bind",
    "bind_production_30s_context_class",
    "active_or_last_30s_provider",
    "production_30s_health",
    "safe_activate_production_30s",
    "activate_production_30s_evidence",
    "install_session_aware_vwap_evidence",
    "install_session_aware_vwap_record_diagnostics",
    "install_session_aware_primary_vwap",
    "session_aware_primary_vwap_context",
    "session_vwap_last",
    "session_vwap_finite",
    "install_cascade_runway_evidence",
    "build_cascade_runway",
    "summarize_cascade_runway",
    "cascade_runway_local_status",
    "cascade_runway_existing_status",
    "cascade_runway_status_payload",
    "cascade_runway_number",
    "CASCADE_RUNWAY_ORDER",
    "CASCADE_RUNWAY_AUTHORITY",
    "CASCADE_RUNWAY_SOURCE",
    "st_flip_compression",
    "st_flip_next_frame_context",
    "st_flip_supporting_flow",
    "st_flip_cluster_span_pct",
    "st_flip_consecutive_recent_rungs",
    "st_flip_timeframe_detail",
    "st_flip_number",
    "ST_FLIP_EARLY_LADDER",
    "install_price_trajectory_metrics",
    "price_trajectory_metrics",
    "PRICE_TRAJECTORY_DISCOVERY_OWNER",
    "install_sparse_history_bridge",
    "bridge_sparse_history_rows",
    "sparse_history_current_bar_count",
    "sparse_history_frame",
    "sparse_history_symbols",
    "SPARSE_HISTORY_AUTHORITY",
    "SPARSE_HISTORY_CURRENT_REASON",
    "SPARSE_HISTORY_BRIDGE_REASON",
    "SPARSE_HISTORY_MIN_REAL_SESSION_BARS",
    "SPARSE_HISTORY_LEGACY_OUTER_GATE_BARS",
    "SPARSE_HISTORY_LOOKBACK_DAYS",
    "SPARSE_HISTORY_BAR_LIMIT",
    "install_convergence_handoff_evidence",
    "build_efficient_maturation_evidence",
    "confirmation_details_with_maturation",
    "CONVERGENCE_HANDOFF_AUTHORITY",
    "CONVERGENCE_HANDOFF_SOURCE",
    "install_catalyst_company_scale_evidence",
    "install_catalyst_scale_analyzed_context",
    "install_catalyst_scale_prefilter_reference",
    "install_catalyst_scale_snapshot_reference",
    "company_scale_context",
    "market_cap_reference",
    "CATALYST_SCALE_AUTHORITY",
    "analyze_candidates",
    "install_strategy_leader_awareness",
    "publish_strategy_leader_awareness",
    "merge_strategy_leader_events",
    "strategy_leader_rows",
    "implied_previous_close",
    "install_market_event_capture",
    "completed_scan_market_events",
    "activate_high_liquidity_trend_watch",
    "high_liquidity_trend_rows",
    "market_event_rows",
    "base_market_event_rows",
    "_LATEST_MARKET_EVENTS",
    "STRATEGY_LEADER_LIMIT",
    "STRATEGY_LEADER_PRICE_CEILING",
    "STRATEGY_LEADER_MAX_DAY_GAINER_RANK",
    "STRATEGY_LEADER_MIN_GAIN_PCT",
    "LIQUIDITY_TREND_LIMIT",
    "LIQUIDITY_TREND_MAX_RANK",
    "LIQUIDITY_TREND_MAX_PRICE",
    "LIQUIDITY_TREND_MIN_VOLUME",
    "LIQUIDITY_TREND_MIN_GAIN_PCT",
    "MARKET_EVENT_LIMIT",
    "EXTREME_MOVER_PCT",
    "ignition_evidence",
    "IGNITION_RECLAIM_RECENT_BARS",
    "IGNITION_FLIP_RECENT_SECONDS",
    "IGNITION_MAX_VWAP_DISTANCE_PCT",
    "reset_leader_memory",
    "apply_leader_reset_marks",
    "leader_reset_evidence",
    "LeaderMemory",
    "THREE_MINUTE_CONFIRMATION",
    "REIGNITION",
    "RESET_WATCH",
    "MAX_REIGNITION_VWAP_DISTANCE_PCT",
    "MIN_LEADER_DOLLAR_FLOW_ACCELERATION",
    "MIN_LEADER_VOLUME_ACCELERATION",
    "MIN_LEADER_PARTICIPATION",
    "LEADER_MEMORY_TTL_SECONDS",
    "NEAR_VWAP_WINDOW_PCT",
    "PROVEN_LEADER_EXTENSION_PCT",
    "install_retest_event_memory",
    "memory_adjusted_retest_truth",
    "retest_event_from_record",
    "reconstruct_three_minute_retest",
    "latest_held_retest",
    "three_minute_st_retest_truth",
    "base_three_minute_st_retest_truth",
    "RETEST_MEMORY_AUTHORITY",
    "RETEST_TRUTH_AUTHORITY",
    "apply_scanner_v2",
    "expansion_candidate_diagnostic",
    "participation_gate_rejection_diagnostics",
    "strengthening_diagnostics",
]

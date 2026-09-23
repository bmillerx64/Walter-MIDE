"""Authority boundary for Market Evidence.

This component owns the seam where raw/derived market observations are assembled.
During Phase 1 it delegates to the current validated analyzers without changing
thresholds, formulas, ordering, or evidence semantics.
"""

from collections.abc import Iterable, Mapping
from copy import deepcopy
from dataclasses import dataclass
from functools import wraps
from time import monotonic
from typing import Any

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


__all__ = [
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

"""Authority boundary for Market Evidence.

This component owns the seam where raw/derived market observations are assembled.
During Phase 1 it delegates to the current validated analyzers without changing
thresholds, formulas, ordering, or evidence semantics.
"""

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

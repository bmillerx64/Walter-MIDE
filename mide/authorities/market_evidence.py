"""Authority boundary for Market Evidence.

This component owns the seam where raw/derived market observations are assembled.
During Phase 1 it delegates to the current validated analyzers without changing
thresholds, formulas, ordering, or evidence semantics.
"""

from functools import wraps
from typing import Any

import pandas as pd

from mide.discovery import analyze_candidates
from mide.decision_engine import expansion_candidate_diagnostic
from mide.scanner_v2 import (
    apply_scanner_v2,
    participation_gate_rejection_diagnostics,
    strengthening_diagnostics,
)

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


__all__ = [
    "analyze_candidates",
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

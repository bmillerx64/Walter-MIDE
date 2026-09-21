"""GS514: remember a valid 3-minute SuperTrend retest after price bounces away.

Sep. 21 NCPL live validation exposed a narrow but important operator-memory gap.
NCPL's 3-minute candle low reached ~1.05 while the bullish 3m SuperTrend line was
~1.0457, then price rebounded toward 1.15. GS493 could only compare *current* price
with the *current* 3m ST line, so after the bounce Walter could say "NOT AT 3M ST YET"
even though the retest had already happened and held.

GS514 reconstructs the latest held 3m ST retest from the same current-session 1-minute
bars GS421 already captured. A retest is remembered only inside the current uninterrupted
bullish 3m SuperTrend regime, using GS462's existing 2% near-ST band. A bearish 3m turn
invalidates the memory; a later bullish regime must earn a new retest.

The memory changes presentation only. It does not grant entry, readiness, qualification,
ranking, audio, execution, or order authority. Walter can therefore distinguish:

    thesis checkpoint happened -> lower-timeframe trigger still incomplete

from the incorrect statement that the 3m retest never occurred.
"""
from __future__ import annotations

from copy import deepcopy
from functools import wraps
from typing import Any

import pandas as pd

from . import gs421_multitimeframe_convergence_recorder as gs421
from . import gs493_3m_st_retest_truth as gs493
from . import gs378_live_vwap_st_crossover as gs378
from .gs462_preflip_ignition_watch import NEAR_ST_LINE_PCT, _timeframe_detail
from .indicators import supertrend

AUTHORITY = "PRESENTATION_MEMORY_ONLY"
_OWNER_BUILD = "_walter_gs514_retest_event_memory_build"
_OWNER_TRUTH = "_walter_gs514_retest_event_memory_truth"
_OWNER_STATE = "_walter_gs514_retest_event_memory_state"


def _number(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if pd.isna(number):
        return None
    return number


def _latest_held_retest(
    tf: pd.DataFrame,
    st_line: pd.Series,
    trend: pd.Series,
    *,
    observed_at: pd.Timestamp,
) -> dict:
    """Return the latest held retest inside the current uninterrupted bullish run."""
    if tf is None or tf.empty or st_line is None or trend is None:
        return {"available": False, "active_memory": False, "authority": AUTHORITY}

    common = tf.index.intersection(st_line.index).intersection(trend.index)
    if len(common) == 0:
        return {"available": False, "active_memory": False, "authority": AUTHORITY}

    frame = tf.loc[common]
    st = st_line.loc[common]
    bullish = trend.loc[common].fillna(False).astype(bool)
    if not bool(bullish.iloc[-1]):
        return {
            "available": False,
            "active_memory": False,
            "invalidated": True,
            "invalidation_reason": "current 3m SuperTrend is bearish",
            "authority": AUTHORITY,
        }

    # Restrict the search to the current uninterrupted bullish regime. This prevents
    # an old retest from surviving a bearish break and then being reused after a later
    # bullish flip.
    last_false_position = -1
    for position, value in enumerate(bullish.tolist()):
        if not value:
            last_false_position = position
    run_start_position = last_false_position + 1

    lows = pd.to_numeric(frame["low"], errors="coerce")
    closes = pd.to_numeric(frame["close"], errors="coerce")
    st_numeric = pd.to_numeric(st, errors="coerce")

    valid = (
        bullish
        & lows.notna()
        & closes.notna()
        & st_numeric.notna()
        & (st_numeric > 0)
    )
    low_gap_pct = (lows - st_numeric) / st_numeric * 100.0
    held = (
        valid
        & (low_gap_pct.abs() <= float(NEAR_ST_LINE_PCT))
        & (closes >= st_numeric)
    )

    # Do not let a retest from a prior bullish regime leak into the current one.
    if run_start_position > 0:
        held.iloc[:run_start_position] = False

    hits = list(held[held].index)
    if not hits:
        return {
            "available": False,
            "active_memory": False,
            "current_three_minute_bullish": True,
            "bullish_run_start_timestamp": common[run_start_position].isoformat(),
            "near_st_line_limit_pct": NEAR_ST_LINE_PCT,
            "authority": AUTHORITY,
        }

    stamp = hits[-1]
    position = common.get_loc(stamp)
    low = _number(lows.loc[stamp])
    close = _number(closes.loc[stamp])
    retest_st = _number(st_numeric.loc[stamp])
    signed_low_gap = _number(low_gap_pct.loc[stamp])

    current_close = _number(closes.iloc[-1])
    current_st = _number(st_numeric.iloc[-1])
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

    return {
        "available": True,
        "active_memory": active_memory,
        "timestamp": pd.Timestamp(stamp).isoformat(),
        "age_seconds": round(age_seconds, 1),
        "bars_since_retest": max(0, len(common) - 1 - int(position)),
        "retest_low": low,
        "retest_close": close,
        "supertrend_at_retest": retest_st,
        "signed_low_gap_pct": (
            round(signed_low_gap, 3) if signed_low_gap is not None else None
        ),
        "current_close": current_close,
        "current_supertrend": current_st,
        "current_gap_pct": round(current_gap, 3) if current_gap is not None else None,
        "current_three_minute_bullish": current_bullish,
        "current_bar_is_retest": bool(stamp == common[-1]),
        "bullish_run_start_timestamp": common[run_start_position].isoformat(),
        "near_st_line_limit_pct": NEAR_ST_LINE_PCT,
        "source": gs421.SOURCE,
        "authority": AUTHORITY,
        "entry_authority_changed": False,
        "readiness_authority_changed": False,
        "ranking_changed": False,
        "audio_changed": False,
    }


def reconstruct_three_minute_retest(raw_rows, client) -> dict:
    """Reconstruct held-retest memory from GS421's already-captured current-session bars."""
    try:
        frame = client.bars_frame(raw_rows or [])
        context = gs378.primary_vwap_context(frame)
        day = context.get("day")
        if day is None or day.empty:
            return {"available": False, "active_memory": False, "authority": AUTHORITY}
        tf = gs421._timeframe_frame(day, "3m")
        if tf is None or tf.empty:
            return {"available": False, "active_memory": False, "authority": AUTHORITY}
        st_line, trend = supertrend(tf, 10, 3)
        observed_at = pd.Timestamp(day.index[-1])
        return _latest_held_retest(
            tf,
            st_line,
            trend,
            observed_at=observed_at,
        )
    except Exception as exc:
        return {
            "available": False,
            "active_memory": False,
            "error_type": type(exc).__name__,
            "authority": AUTHORITY,
        }


def _event_from_record(record: dict) -> dict:
    maturation = record.get("multitimeframe_maturation") or {}
    if not isinstance(maturation, dict):
        return {}
    event = maturation.get("three_minute_st_retest_event") or {}
    return event if isinstance(event, dict) else {}


def _fmt_price(value: Any) -> str:
    number = _number(value)
    if number is None:
        return "n/a"
    if abs(number) < 1:
        return f"{number:.4f}"
    if abs(number) < 10:
        return f"{number:.3f}"
    return f"{number:.2f}"


def _supportive(record: dict, label: str) -> bool:
    detail = _timeframe_detail(record, label)
    return bool(
        detail.get("available")
        and detail.get("bullish")
        and detail.get("above_vwap")
    )


def discipline_sequence(record: dict, event: dict) -> dict:
    """Describe thesis-vs-trigger sequencing without creating entry authority."""
    relation = str(record.get("vwap_relation") or "").strip().lower()
    distance = _number(record.get("vwap_distance_pct"))
    near_vwap = bool(
        relation == "above"
        and (distance is None or distance <= 2.0)
    )
    thirty = _supportive(record, "30s")
    one = _supportive(record, "1m")
    repaired = bool(near_vwap and thirty and one)
    return {
        "three_minute_retest_held": bool(event.get("active_memory")),
        "vwap_acceptance": near_vwap,
        "thirty_second_repaired": thirty,
        "one_minute_repaired": one,
        "lower_timeframe_repair_complete": repaired,
        "state": (
            "THESIS_HELD_TRIGGER_REPAIRED"
            if repaired
            else "THESIS_HELD_TRIGGER_INCOMPLETE"
        ),
        "authority": AUTHORITY,
        "entry_authority_changed": False,
        "readiness_authority_changed": False,
    }


def _memory_truth(original, record: dict) -> dict:
    truth = dict(original(record))
    event = _event_from_record(record)
    if (
        truth.get("state") in {"NOT_AT_3M_ST_YET", "ST_RETEST_CONFIRMED"}
        and event.get("available")
        and event.get("active_memory")
    ):
        truth["state"] = "PRIOR_ST_RETEST_HELD"
        truth["prior_retest_event"] = dict(event)
        truth["authority"] = AUTHORITY
        truth["entry_authority_changed"] = False
        truth["readiness_authority_changed"] = False
    return truth



def install() -> None:
    """Install retest reconstruction plus presentation memory after GS421/GS422/GS493."""
    current_build = gs421.build_maturation_evidence
    if not getattr(current_build, _OWNER_BUILD, False):
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
            updated["three_minute_st_retest_memory_authority"] = AUTHORITY
            return updated

        setattr(build_with_retest, _OWNER_BUILD, True)
        build_with_retest._gs514_original = current_build
        gs421.build_maturation_evidence = build_with_retest

    current_truth = gs493.three_minute_st_retest_truth
    if not getattr(current_truth, _OWNER_TRUTH, False):
        @wraps(current_truth)
        def truth_with_memory(record: dict) -> dict:
            return _memory_truth(current_truth, record)

        setattr(truth_with_memory, _OWNER_TRUTH, True)
        truth_with_memory._gs514_original = current_truth
        gs493.three_minute_st_retest_truth = truth_with_memory

    current_state = gs493.state_with_3m_st_truth
    if not getattr(current_state, _OWNER_STATE, False):
        # Preserve GS493's established wrapper signature:
        # (original_opportunity_state_callable, record).
        @wraps(current_state)
        def bound_state(original, record: dict) -> dict:
            view = current_state(original, record)
            truth = dict(view.get("three_minute_st_retest_truth") or {})
            if truth.get("state") != "PRIOR_ST_RETEST_HELD":
                return view

            event = dict(truth.get("prior_retest_event") or _event_from_record(record))
            sequence = discipline_sequence(record, event)
            result = deepcopy(view)
            result["discipline_sequence"] = sequence

            age = _number(event.get("age_seconds"))
            age_text = f"{age / 60.0:.0f}m ago" if age is not None else "earlier"
            low_text = _fmt_price(event.get("retest_low"))
            st_text = _fmt_price(event.get("supertrend_at_retest"))
            if sequence["lower_timeframe_repair_complete"]:
                guardrail = (
                    f"PRIOR 3M ST RETEST HELD: low {low_text} tested the 3m SuperTrend "
                    f"{st_text} {age_text} inside the existing {NEAR_ST_LINE_PCT:.0f}% band. "
                    "Lower-timeframe VWAP/30s/1m repair is now present; review the chart, "
                    "but existing readiness and entry authority still control."
                )
            else:
                missing = []
                if not sequence["vwap_acceptance"]:
                    missing.append("VWAP acceptance")
                if not sequence["thirty_second_repaired"]:
                    missing.append("30s repair")
                if not sequence["one_minute_repaired"]:
                    missing.append("1m repair")
                guardrail = (
                    f"PRIOR 3M ST RETEST HELD: low {low_text} tested the 3m SuperTrend "
                    f"{st_text} {age_text}. Thesis checkpoint confirmed; entry trigger is "
                    "NOT earned yet. Still need " + ", ".join(missing) + "."
                )
            next_step = str(result.get("next_step") or "").strip()
            if "PRIOR 3M ST RETEST HELD:" not in next_step:
                result["next_step"] = f"{guardrail} {next_step}".strip()
            return result

        setattr(bound_state, _OWNER_STATE, True)
        bound_state._gs514_original = current_state
        gs493.state_with_3m_st_truth = bound_state

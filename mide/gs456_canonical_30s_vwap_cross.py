"""GS456: preserve canonical 30s VWAP and literal ST/VWAP line-cross truth.

RETO live validation on 2026-09-15 exposed a final ambiguity in the first rung of
Walter's maturation ladder. Webull's 30-second chart can display VWAP as 0.0000 even
while its chart price/SuperTrend behavior is obviously live. Walter must not depend on
that presentation value.

Walter already has the ingredients locally: GS397 feeds genuine completed Webull
TICK-reconstructed 30s bars into GS378's alignment pass, and that pass already computes
both session VWAP and SuperTrend(10,3). Before GS456, the numeric 30s VWAP and literal
ST-line/VWAP-line crossing were discarded, and GS397 later preferred the broader
Stage-6 VWAP when rebuilding the canonical 30s above-VWAP flag.

GS456 replaces only the 30s alignment helper so the already-paid calculation retains:
- Walter's normal 09:30 ET RTH / 04:00 ET premarket VWAP policy,
- the numeric 30s VWAP and current 30s SuperTrend values,
- a deterministic literal 30s ST-line/VWAP-line cross event,
- the same alignment fields GS397 already consumes.

GS397 then prefers that canonical 30s VWAP truth, and GS455's first maturation rung
prefers the literal cross when it exists. The established 30s bullish-flip tripwire
remains the fallback when VWAP/crossover evidence is unavailable.

No provider request, extra SuperTrend calculation, entry authority, qualification,
readiness, scoring, execution, or order behavior is added.
"""
from __future__ import annotations

from copy import deepcopy
from functools import wraps
from typing import Any

import pandas as pd

from . import gs378_live_vwap_st_crossover as gs378

AUTHORITY = "CANONICAL_30S_VWAP_CROSS"
SOURCE = "GS397 completed Webull 30s stream bars -> GS378 local VWAP/ST pass"


def _finite(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if pd.notna(number) else None


def _empty_30s_alignment() -> dict:
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
        "authority": AUTHORITY,
        "source": SOURCE,
    }


def alignment_30s_truth(frame_30s: pd.DataFrame | None) -> dict:
    """Compute and retain 30s VWAP/ST truth in the existing alignment ST pass."""
    from . import gs455_early_ignition_3m_confirmation as gs455

    day = gs378._eastern_day(frame_30s)
    if day.empty:
        return _empty_30s_alignment()

    context = gs378.primary_vwap_context(day)
    day = context.get("day")
    primary = context.get("series")
    if day is None or day.empty or primary is None or primary.empty:
        return _empty_30s_alignment()

    vwap = primary.reindex(day.index)
    close = day["close"].astype(float)
    latest_close = _finite(close.iloc[-1]) if len(close) else None
    latest_vwap = _finite(vwap.iloc[-1]) if len(vwap) else None

    ema65 = gs378.ema(close, 65).iloc[-1] if len(day) >= 65 else float("nan")
    st_line, direction = gs378.supertrend(day, 10, 3)
    latest_st = _finite(st_line.iloc[-1]) if len(st_line) else None
    hh = gs378._higher_highs(day)
    hl = gs378.higher_lows(day) if len(day) >= 4 else None
    structure = None if hh is None or hl is None else bool(hh and hl)

    above_vwap = bool(
        latest_close is not None
        and latest_vwap is not None
        and latest_close >= latest_vwap
    )
    bullish = bool(len(direction) and direction.iloc[-1])
    above_ema = bool(pd.notna(ema65) and latest_close is not None and latest_close >= float(ema65))
    aligned = bool(above_vwap and bullish and above_ema and structure is not False)

    cross = gs455._line_cross_event(
        day,
        vwap,
        st_line,
        direction,
        "30s",
        latest_source_time=day.index[-1],
    )

    anchor = context.get("anchor_time")
    return {
        "above_vwap": above_vwap,
        "supertrend_bullish": bullish,
        "above_ema65": above_ema,
        "higher_highs_higher_lows": structure,
        "aligned": aligned,
        "vwap_value": round(latest_vwap, 6) if latest_vwap is not None else None,
        "vwap_anchor_mode": context.get("anchor_mode"),
        "vwap_anchor_time_et": anchor.isoformat() if anchor is not None else None,
        "supertrend_value": round(latest_st, 6) if latest_st is not None else None,
        "st_vwap_line_cross": cross,
        "authority": AUTHORITY,
        "source": SOURCE,
    }


def alignment_summary_with_30s_truth(
    day_1m: pd.DataFrame,
    primary_1m: pd.Series,
    frame_30s: pd.DataFrame | None = None,
) -> dict:
    """Preserve GS378's 1m/3m contract while retaining canonical 30s values."""
    details: dict[str, dict] = {
        "30s": alignment_30s_truth(frame_30s),
        "1m": gs378._alignment_evaluation(day_1m, primary_1m, "1m"),
    }
    frame_3m = gs378._timeframe_frame(day_1m, "3m")
    details["3m"] = gs378._alignment_evaluation(frame_3m, primary_1m, "3m")
    score = sum(bool(details[label].get("aligned")) for label in ("30s", "1m", "3m"))
    return {
        "timeframe_alignment": details,
        "alignment_score": score,
        "alignment_total": 3,
        "alignment_label": gs378._ALIGNMENT_LABELS[score],
    }


def _install_alignment_truth() -> None:
    current = gs378._alignment_summary
    if getattr(current, "_gs456_canonical_30s_vwap", False):
        return
    alignment_summary_with_30s_truth._gs456_canonical_30s_vwap = True
    alignment_summary_with_30s_truth._gs456_original = current
    gs378._alignment_summary = alignment_summary_with_30s_truth


def _install_gs397_canonicalization() -> None:
    from . import gs397_canonical_30s_tripwire_truth as gs397

    current_above = gs397._primary_above_vwap
    if not getattr(current_above, "_gs456_canonical_30s_vwap", False):
        @wraps(current_above)
        def primary_above_vwap(record: dict, alignment_30s: dict, tripwire: dict):
            close = _finite(tripwire.get("latest_close"))
            vwap = _finite(alignment_30s.get("vwap_value"))
            if close is not None and vwap is not None:
                return close >= vwap
            if alignment_30s.get("above_vwap") is not None and alignment_30s.get("authority") == AUTHORITY:
                return bool(alignment_30s.get("above_vwap"))
            return current_above(record, alignment_30s, tripwire)

        primary_above_vwap._gs456_canonical_30s_vwap = True
        primary_above_vwap._gs456_original = current_above
        gs397._primary_above_vwap = primary_above_vwap

    current_canonicalize = gs397.canonicalize_record
    if getattr(current_canonicalize, "_gs456_canonical_30s_vwap", False):
        return

    @wraps(current_canonicalize)
    def canonicalize_record(record: dict) -> dict:
        updated = current_canonicalize(record)
        alignment = deepcopy(updated.get("timeframe_alignment") or {})
        thirty = dict(alignment.get("30s") or {})
        if thirty.get("authority") != AUTHORITY:
            return updated

        cross = deepcopy(thirty.get("st_vwap_line_cross") or {})
        updated["vwap_30s_value"] = thirty.get("vwap_value")
        updated["vwap_30s_anchor_mode"] = thirty.get("vwap_anchor_mode")
        updated["vwap_30s_anchor_time_et"] = thirty.get("vwap_anchor_time_et")
        updated["st_vwap_30s_line_cross"] = cross

        timeframes = deepcopy(updated.get("timeframes") or {})
        tf30 = dict(timeframes.get("30s") or {})
        tf30.update(
            {
                "vwap_value": thirty.get("vwap_value"),
                "vwap_anchor_mode": thirty.get("vwap_anchor_mode"),
                "vwap_anchor_time_et": thirty.get("vwap_anchor_time_et"),
                "supertrend_value": thirty.get("supertrend_value"),
                "st_vwap_line_cross": cross,
                "vwap_truth_authority": AUTHORITY,
            }
        )
        timeframes["30s"] = tf30
        updated["timeframes"] = timeframes
        return updated

    canonicalize_record._gs456_canonical_30s_vwap = True
    canonicalize_record._gs456_original = current_canonicalize
    gs397.canonicalize_record = canonicalize_record


def _install_gs455_first_rung() -> None:
    from . import gs455_early_ignition_3m_confirmation as gs455

    current = gs455._thirty_second_rung
    if getattr(current, "_gs456_literal_30s_cross", False):
        return

    @wraps(current)
    def thirty_second_rung(record: dict) -> dict:
        event = dict(record.get("st_vwap_30s_line_cross") or {})
        if not event:
            alignment = record.get("timeframe_alignment") or {}
            event = dict((alignment.get("30s") or {}).get("st_vwap_line_cross") or {})
        if event.get("crossed") and event.get("current_confirmed"):
            event["kind"] = "literal_30s_st_vwap_line_cross"
            return event
        fallback = dict(current(record))
        fallback.setdefault("kind", "canonical_30s_tripwire_flip_fallback")
        return fallback

    thirty_second_rung._gs456_literal_30s_cross = True
    thirty_second_rung._gs456_original = current
    gs455._thirty_second_rung = thirty_second_rung


def install() -> None:
    """Install canonical 30s VWAP/crossover truth without adding hot-path work."""
    _install_alignment_truth()
    _install_gs397_canonicalization()
    _install_gs455_first_rung()

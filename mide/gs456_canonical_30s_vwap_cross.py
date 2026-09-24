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
- whichever primary VWAP policy is canonically installed at runtime (GS391 currently
  owns live Webull parity with its extended-session 04:00 ET anchor),
- the numeric 30s VWAP and current 30s SuperTrend values,
- a deterministic literal 30s ST-line/VWAP-line cross event,
- the same alignment fields GS397 already consumes.

GS397 then prefers that canonical 30s VWAP truth, and GS455's first maturation rung
prefers the literal cross when it exists. The established 30s bullish-flip tripwire
remains the fallback when VWAP/crossover evidence is unavailable. VWAP-truth authority
is stored separately from GS397's tripwire authority so neither layer overwrites the
other.

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
SOURCE = "GS397 completed Webull 30s stream bars -> installed canonical VWAP/ST pass"


def _finite(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if pd.notna(number) else None


def _market_evidence():
    from mide.authorities import market_evidence

    return market_evidence


def _empty_30s_alignment() -> dict:
    current = getattr(
        _market_evidence(),
        "canonical_30s_empty_alignment",
        None,
    )
    if callable(current):
        return current()
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
        "vwap_truth_authority": AUTHORITY,
        "source": SOURCE,
    }


def alignment_30s_truth(
    frame_30s: pd.DataFrame | None,
) -> dict:
    current = getattr(
        _market_evidence(),
        "canonical_30s_alignment_truth",
        None,
    )
    if not callable(current):
        return _empty_30s_alignment()
    return current(frame_30s)


def alignment_summary_with_30s_truth(
    day_1m: pd.DataFrame,
    primary_1m: pd.Series,
    frame_30s: pd.DataFrame | None = None,
) -> dict:
    current = getattr(
        _market_evidence(),
        "canonical_alignment_summary_with_30s_truth",
        None,
    )
    if not callable(current):
        return gs378._alignment_summary(
            day_1m,
            primary_1m,
            frame_30s,
        )
    return current(
        day_1m,
        primary_1m,
        frame_30s,
    )


def _install_alignment_truth() -> None:
    current = getattr(
        _market_evidence(),
        "install_canonical_30s_alignment_truth",
        None,
    )
    if callable(current):
        current()


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
            if (
                alignment_30s.get("above_vwap") is not None
                and alignment_30s.get("vwap_truth_authority") == AUTHORITY
            ):
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
        if thirty.get("vwap_truth_authority") != AUTHORITY:
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
            event = dict(
                (alignment.get("30s") or {}).get("st_vwap_line_cross") or {}
            )
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

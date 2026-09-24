"""GS553: warm-deploy-safe primary ignition freshness facade.

GS548 corrected literal ST/VWAP maturation for stale source bars. The 2026-09-24
post-transition CAB then proved the parallel GS393 primary-ignition path had two
freshness defects: a same-bar VWAP reclaim age of zero was discarded by a truthiness
fallback, while a reclaim one or two bars old could remain "recent" even when the
newest source bar itself was many minutes stale.

Market Evidence owns the permanent correction. This module is a unique hot-deploy
boundary: if a retained process still exposes the pre-GS553 ignition function, wrap
that exact function with the same source-age correction without changing any entry,
qualification, ranking, execution, or order authority.
"""
from __future__ import annotations

from functools import wraps
from typing import Any


AUTHORITY = "SOURCE_AGE_ADJUSTED_PRIMARY_IGNITION_FRESHNESS"
OWNER = "_gs553_source_aged_primary_ignition"


def _finite(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number


def _correct(record: dict, evidence: dict, market) -> dict:
    result = dict(evidence or {})

    source_age = None
    source_age_fn = getattr(market, "maturation_source_bar_age", None)
    if callable(source_age_fn):
        try:
            source_age = source_age_fn(record)
        except Exception:
            source_age = None
    if source_age is None:
        source_age = _finite(
            record.get("source_bar_age_seconds")
            if record.get("source_bar_age_seconds") is not None
            else record.get("bar_age_seconds")
        )
    if source_age is not None:
        source_age = max(0.0, source_age)

    reclaim_bars = _finite(record.get("vwap_reclaim_age_bars"))
    if reclaim_bars is None:
        reclaim_bars = 999.0
    reclaim_bars = max(0.0, reclaim_bars)

    reclaim_relative_seconds = reclaim_bars * 60.0
    reclaim_effective_seconds = (
        reclaim_relative_seconds + source_age
        if source_age is not None
        else reclaim_relative_seconds
    )
    reclaim_limit = float(getattr(market, "IGNITION_RECLAIM_RECENT_BARS", 2)) * 60.0
    reclaim_recent = bool(
        record.get("vwap_reclaimed_last_10m")
        and reclaim_effective_seconds <= reclaim_limit
    )

    one = {}
    states = record.get("timeframes")
    if isinstance(states, dict) and isinstance(states.get("1m"), dict):
        one = dict(states["1m"])

    detail_flip = _finite(one.get("bullish_flip_age_seconds"))
    gs548_authority = getattr(
        market,
        "GS548_MATURATION_FRESHNESS_AUTHORITY",
        "SOURCE_AGE_ADJUSTED_MATURATION_FRESHNESS",
    )
    if detail_flip is not None and one.get("freshness_authority") == gs548_authority:
        flip_age = max(0.0, detail_flip)
    else:
        raw_flip = _finite(record.get("supertrend_flip_age_seconds"))
        flip_age = (
            max(0.0, raw_flip) + source_age
            if raw_flip is not None and source_age is not None
            else raw_flip
        )

    flip_limit = float(getattr(market, "IGNITION_FLIP_RECENT_SECONDS", 150.0))
    flip_recent = bool(
        flip_age is not None
        and 0.0 <= flip_age <= flip_limit
    )

    supported = bool(result.get("supporting_flow"))
    trigger = None
    if (
        result.get("inside_chase_guard")
        and result.get("one_minute_supertrend_bullish")
        and result.get("one_minute_above_vwap")
        and supported
    ):
        if reclaim_recent:
            trigger = "VWAP_RECLAIM_WITH_BULLISH_1M_ST"
        elif flip_recent:
            trigger = "BULLISH_1M_ST_FLIP_ABOVE_VWAP"

    result.update(
        {
            "recent": trigger is not None,
            "trigger": trigger,
            "vwap_reclaim_recent": reclaim_recent,
            "vwap_reclaim_age_bars": reclaim_bars,
            "vwap_reclaim_source_relative_age_seconds": round(
                reclaim_relative_seconds,
                1,
            ),
            "vwap_reclaim_effective_age_seconds": round(
                reclaim_effective_seconds,
                1,
            ),
            "source_bar_age_seconds": (
                round(source_age, 1)
                if source_age is not None
                else None
            ),
            "one_minute_bullish_flip_recent": flip_recent,
            "one_minute_bullish_flip_age_seconds": (
                round(flip_age, 1)
                if flip_age is not None
                else None
            ),
            "freshness_authority": AUTHORITY,
        }
    )
    return result


def install() -> bool:
    """Install GS553 exactly once on a retained Market Evidence generation."""
    from mide.authorities import market_evidence as market

    current = market.ignition_evidence
    if getattr(current, OWNER, False):
        return False

    @wraps(current)
    def source_fresh_ignition(record: dict) -> dict:
        return _correct(
            record,
            current(record),
            market,
        )

    setattr(source_fresh_ignition, OWNER, True)
    source_fresh_ignition._gs553_original = current
    market.ignition_evidence = source_fresh_ignition
    return True


__all__ = ["AUTHORITY", "OWNER", "install"]

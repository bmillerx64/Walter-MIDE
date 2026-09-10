"""GS423: finish the TNON convergence recorder without keeping Walter slow.

Sep. 10 close validation of GS422 proved two things at once:
* selective GS421 work improved median scan time, but the remaining studied records
  still repeated SuperTrend calculations that GS378 had already performed; and
* the completed Flight Recorder contained no ``multitimeframe_maturation`` package,
  so the live learning payload was not surviving the actual analysis path.

GS423 makes the handoff explicit.  GS378's existing 1m/3m/5m/10m confirmation pass
now retains the bullish-flip metadata it already had in memory, and the live GS423
handoff reuses that metadata. Only the missing 15m maturation requires another
SuperTrend pass for a selected study record. A GS423-owned application wrapper also
replaces any inherited or stale GS421 application wrapper after a warm Streamlit
deploy, guaranteeing that every analyzed record receives either a real observational
package or an explicit skipped package before it enters the architecture handoff.

The standalone GS421 helper remains unchanged for replay/unit compatibility; the live
GS423 wrapper calls the efficient builder directly. This remains observational only.
Confirmation counts and established trading fields are preserved; discovery, scoring,
ranking, qualification, readiness, thresholds, VWAP/chase rules, alerts/audio,
execution, orders, and provider requests are unchanged.
"""
from __future__ import annotations

from functools import wraps
from typing import Any

import pandas as pd

from . import gs378_live_vwap_st_crossover as gs378
from . import gs421_multitimeframe_convergence_recorder as gs421
from . import gs422_convergence_recorder_performance as gs422

AUTHORITY = "OBSERVATIONAL_ONLY"
SOURCE = (
    "GS378 already-computed 1m/3m/5m/10m state plus one local 15m maturation pass; "
    "no additional provider history request"
)
_INSTALL_GENERATION = object()


def _number(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if pd.notna(number) else None


def confirmation_details_with_maturation(
    day: pd.DataFrame, primary_series: pd.Series
) -> tuple[int, dict]:
    """Preserve GS378 confirmation truth while retaining its already-computed flip data."""
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
            # Existing GS378 contract consumed by live scoring/UI.
            "above_vwap": above_vwap,
            "supertrend": bullish,
            # Additive GS421/423 observational contract.
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
            flip_price = _number(close.loc[flip_time])
            flip_vwap = _number(vwap.loc[flip_time])
            detail.update(
                {
                    "price_at_flip": flip_price,
                    "vwap_at_flip": flip_vwap,
                    "vwap_distance_at_flip_pct": (
                        round((flip_price - flip_vwap) / flip_vwap * 100.0, 4)
                        if flip_price is not None and flip_vwap not in (None, 0)
                        else None
                    ),
                    "supertrend_at_flip": _number(st_line.loc[flip_time]),
                    "volume_at_flip": _number(tf.loc[flip_time, "volume"]),
                }
            )
        details[label] = detail

    return confirmations, details


def _fallback_event(record: dict, label: str) -> dict:
    """Reuse GS378 1m/3m event truth when a confirmation detail is unavailable."""
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
        # GS378's crossover price is not necessarily the bullish-flip price, so do
        # not relabel it. The normal live path receives exact values from the enriched
        # confirmation pass above.
        "price_at_flip": None,
        "vwap_at_flip": None,
        "supertrend_at_flip": None,
        "volume_at_flip": None,
    }


def build_efficient_maturation_evidence(record: dict, raw_rows, client) -> dict:
    """Build live GS421 evidence with zero duplicate 1m/3m/5m/10m ST calculations."""
    if not gs422.should_record_maturation(record):
        return gs422.skipped_evidence(record)

    frame = client.bars_frame(raw_rows or [])
    context = gs378.primary_vwap_context(frame)
    day = context.get("day")
    primary = context.get("series")
    if day is None or day.empty or primary is None or primary.empty:
        return {
            "authority": AUTHORITY,
            "source": SOURCE,
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
            events[label] = _fallback_event(record, label)
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

    # GS378 already paid for every faster timeframe above. 15m is the only missing
    # maturation layer and remains observational / study-selected by GS422.
    events["15m"] = gs421._timeframe_event(day, primary, "15m")

    cascade = gs421._cascade(events)
    current_confirmed = [
        label
        for label in gs421.MATURATION_ORDER
        if (events.get(label) or {}).get("current_confirmed")
    ]
    one_minute = events.get("1m") or {}
    return {
        "authority": AUTHORITY,
        "source": SOURCE,
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
            "last_flip_age_seconds": _number(
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
            "price": _number(record.get("price")),
            "vwap_distance_pct": _number(record.get("vwap_distance_pct")),
            "participation_score": _number(record.get("participation_score")),
            "participation_surge_score": _number(record.get("participation_surge_score")),
            "expansion_score": _number(record.get("expansion_score")),
            "volume_acceleration": _number(record.get("volume_acceleration")),
            "dollar_flow_acceleration": _number(record.get("dollar_flow_acceleration")),
            "qualified_for_watch": bool(record.get("qualified_for_watch")),
            "qualified_for_entry": bool(record.get("qualified_for_entry")),
            "status": record.get("status"),
        },
    }


def _inherit(wrapper, wrapped) -> None:
    for name, value in getattr(wrapped, "__dict__", {}).items():
        if name.startswith("_gs") and not hasattr(wrapper, name):
            setattr(wrapper, name, value)


def install() -> None:
    """Own the current convergence application boundary after the GS421/422 chain."""
    current = gs378.apply_live_vwap_truth
    if getattr(current, "_gs423_install_generation", None) is _INSTALL_GENERATION:
        return

    # Replace the stale/older GS421 application wrapper rather than stacking another
    # full maturation pass around it. The pure GS378 correction remains the base.
    base = getattr(current, "_gs423_base", None)
    if not callable(base):
        base = getattr(current, "_gs421_original", current)

    # Enrich GS378's existing confirmation calculation itself. This does not add a
    # SuperTrend call; it only retains metadata from the four calls already required.
    gs378._confirmation_details = confirmation_details_with_maturation

    @wraps(base)
    def apply_with_efficient_maturation(
        records, current_session_raw, current_session_30s_raw, client
    ):
        updated = base(records, current_session_raw, current_session_30s_raw, client)
        studied = 0
        skipped = 0
        for record in updated or []:
            symbol = str(record.get("symbol") or "").strip().upper()
            if not symbol:
                continue
            evidence = build_efficient_maturation_evidence(
                record,
                (current_session_raw or {}).get(symbol) or [],
                client,
            )
            record["multitimeframe_maturation"] = evidence
            record["multitimeframe_maturation_authority"] = AUTHORITY
            if evidence.get("skipped"):
                skipped += 1
            elif evidence.get("available"):
                studied += 1

        diagnostics = getattr(client, "diagnostics", None)
        if isinstance(diagnostics, dict):
            diagnostics["gs423_convergence_handoff_efficiency"] = {
                "authority": AUTHORITY,
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

    _inherit(apply_with_efficient_maturation, base)
    # Preserve the compatibility marker so an inherited GS421 application wrapper
    # cannot stack itself over this final live boundary on a warm rerun. The pure
    # GS421 helper itself is intentionally left unchanged.
    apply_with_efficient_maturation._gs421_multitimeframe_convergence = True
    apply_with_efficient_maturation._gs423_convergence_handoff_efficiency = True
    apply_with_efficient_maturation._gs423_install_generation = _INSTALL_GENERATION
    apply_with_efficient_maturation._gs423_base = base
    apply_with_efficient_maturation._gs421_original = base
    gs378.apply_live_vwap_truth = apply_with_efficient_maturation

"""GS468: hard-stop false urgency when current numeric VWAP truth says below.

Live validation on 2026-09-16 exposed a trader-facing contradiction on JZXN. The
Opportunity State card described VWAP as "Above / within 2%" and could transiently
surface LOOK NOW even though the operator's current Webull chart showed price
materially below VWAP. GS310 already refuses urgency when ``vwap_relation`` is
``below``; the missing invariant was that downstream state wrappers trusted that
categorical field without reconciling it against the numeric current price/VWAP
values already carried in the record.

GS468 adds one final presentation-state veto. It does not change acquisition,
indicator math, scoring, qualification, readiness, alerts, execution, or orders.
When existing numeric evidence proves current price is below current VWAP, the final
trader-facing state cannot be LOOK NOW or WATCH FOR ENTRY and the VWAP checklist is
rendered as not above. When numeric evidence is unavailable or non-contradictory,
existing semantics are preserved.

The veto uses two already-computed current pairs when available:
* top-level snapshot ``price`` versus authoritative ``vwap_value``;
* current 1m close versus current 1m VWAP from ``timeframes['1m']``.

Either pair proving price below VWAP is enough to block urgency. This is intentionally
conservative: Walter may keep watching a symbol below VWAP, but it must not tell the
operator to LOOK NOW for an entry-style setup until VWAP is actually reclaimed.
"""
from __future__ import annotations

from copy import deepcopy
from functools import wraps
import math
from typing import Any

_OWNER_ATTR = "_walter_gs468_vwap_truth_veto_owner"
_PROVENANCE = "GS468_NUMERIC_VWAP_VETO"


def _finite(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _pair(close: Any, vwap: Any, source: str) -> dict:
    close_n = _finite(close)
    vwap_n = _finite(vwap)
    available = close_n is not None and vwap_n not in (None, 0.0)
    if not available:
        return {
            "source": source,
            "available": False,
            "close": close_n,
            "vwap": vwap_n,
            "distance_pct": None,
            "above": None,
        }
    distance = (close_n - vwap_n) / vwap_n * 100.0
    return {
        "source": source,
        "available": True,
        "close": close_n,
        "vwap": vwap_n,
        "distance_pct": round(distance, 4),
        "above": bool(distance >= 0.0),
    }


def current_vwap_truth(record: dict) -> dict:
    """Return already-computed current numeric VWAP evidence without new data calls."""
    top = _pair(
        record.get("price"),
        record.get("vwap_value"),
        "snapshot_vs_primary_vwap",
    )

    one = dict((record.get("timeframes") or {}).get("1m") or {})
    one_close = one.get("current_close")
    one_vwap = one.get("current_vwap")
    if one_vwap is None:
        one_vwap = dict(one.get("st_vwap_line_cross") or {}).get("latest_vwap_value")
    one_pair = _pair(one_close, one_vwap, "1m_close_vs_primary_vwap")

    pairs = [item for item in (top, one_pair) if item.get("available")]
    below = [item for item in pairs if item.get("above") is False]
    above = [item for item in pairs if item.get("above") is True]
    return {
        "pairs": pairs,
        "numeric_below": bool(below),
        "numeric_above": bool(above),
        "below_sources": [item["source"] for item in below],
        "authority": "PRESENTATION_TRUTH_VETO_ONLY",
        "additional_market_data_requests": 0,
    }


def _numeric_below_record(record: dict, truth: dict) -> dict:
    """Return a detached state-input copy whose VWAP fields cannot contradict numbers."""
    view_record = deepcopy(record)
    pairs = list(truth.get("pairs") or [])
    below = [item for item in pairs if item.get("above") is False]
    if not below:
        return view_record

    # Prefer the live snapshot/current primary pair for the displayed distance. Fall
    # back to 1m only when the top-level numeric pair is unavailable.
    chosen = next(
        (item for item in below if item.get("source") == "snapshot_vs_primary_vwap"),
        below[0],
    )
    view_record["vwap_relation"] = "below"
    distance = _finite(chosen.get("distance_pct"))
    if distance is not None:
        view_record["vwap_distance_pct"] = round(distance, 4)
    return view_record


def vwap_truth_state(original, record: dict) -> dict:
    """Apply a numeric-below veto before the final trader-facing state is returned."""
    from . import gs310_unified_opportunity_state as unified

    truth = current_vwap_truth(record)
    if not truth.get("numeric_below"):
        return original(record)

    # Re-run the existing state translation on a detached copy with truthful VWAP
    # relation/distance. This naturally yields DEVELOPING through GS310's existing
    # below-VWAP contract and also makes its checklist say "Not above".
    state = original(_numeric_below_record(record, truth))
    view = deepcopy(state)

    # Later wrappers are not supposed to outrank this function, but preserve the hard
    # invariant even if an inherited legacy state callable returns urgency anyway.
    if str(view.get("state") or "") in {unified.LOOK_NOW, unified.WATCH_FOR_ENTRY}:
        view["state"] = unified.DEVELOPING
        view["color"] = unified.STATE_COLORS[unified.DEVELOPING]
        view["reason"] = (
            "Current numeric price/VWAP evidence is below VWAP; Walter will not elevate "
            "this setup until VWAP is reclaimed."
        )
        view["next_step"] = (
            "Keep it on background watch. Reassess only after current price and 1m "
            "structure reclaim VWAP."
        )

    provenance = list(view.get("attention_provenance") or [])
    if _PROVENANCE not in provenance:
        provenance.append(_PROVENANCE)
    view["attention_provenance"] = provenance
    view["vwap_truth_veto"] = truth
    return view


def _inherit(wrapper, wrapped) -> None:
    for name, value in getattr(wrapped, "__dict__", {}).items():
        if name.startswith("_gs") and not hasattr(wrapper, name):
            setattr(wrapper, name, value)


def install() -> None:
    """Install final numeric VWAP veto across all trader-facing state bindings."""
    from . import gs310_unified_opportunity_state as unified
    from . import gs311_unified_voice as voice
    from . import gs314_state_consistency as consistency
    from . import gs363_operator_attention_hierarchy as hierarchy

    current = unified.opportunity_state
    if getattr(current, _OWNER_ATTR, False):
        calibrated = current
    else:
        @wraps(current)
        def calibrated(record: dict) -> dict:
            return vwap_truth_state(current, record)

        _inherit(calibrated, current)
        calibrated._gs468_vwap_truth_veto = True
        calibrated._gs468_original = current
        setattr(calibrated, _OWNER_ATTR, True)
        unified.opportunity_state = calibrated

    voice.opportunity_state = calibrated
    consistency.opportunity_state = calibrated
    hierarchy.opportunity_state = calibrated

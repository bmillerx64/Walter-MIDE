"""GS525: expire stale 30s-derived Developing urgency without losing the stock.

Sept. 22 live validation on GLND exposed a timing/semantics failure. Walter correctly
retained a runner, but could still present a standalone legacy 1m ignition as
DEVELOPING long after the first useful 30s ignition window had passed. That is
technically descriptive but operationally late.

GS525 tightens only trader-facing freshness:

* GS462's 30s pre-flip attention seed expires after five minutes instead of ten.
* A GS467-demoted standalone 1m ignition whose canonical 30s flip is older than five
  minutes is explicitly labeled a LATE CONTINUATION WATCH unless a fresh ordered
  maturation rung has appeared.
* The record remains visible and may immediately become urgent again when fresh 1m/3m
  maturation, reset/retest, reclaim, or other established evidence fires.

No discovery membership, market-data request, score, Mission Rank, qualification,
participation, expansion, readiness, anti-chase, 3m retest, alert permission,
execution, or order behavior changes.
"""
from __future__ import annotations

from copy import deepcopy
from functools import wraps
from typing import Any


FRESH_30S_ATTENTION_SECONDS = 5 * 60.0
_OWNER_ATTR = "_walter_gs525_fresh_attention_expiry_owner"
_PROVENANCE = "GS525_LATE_IGNITION_CONTEXT"


def _number(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def thirty_second_flip_age(record: dict) -> float | None:
    """Return canonical 30s flip age from the live tripwire evidence."""
    age = _number(record.get("supertrend_30s_last_flip_age_seconds"))
    if age is not None:
        return age
    tripwire = record.get("thirty_second_tripwire") or {}
    return _number(tripwire.get("last_flip_age_seconds"))


def fresh_higher_maturation(record: dict) -> bool:
    """Reuse GS455's established fresh-rung truth; invent no new signal."""
    try:
        from . import gs455_early_ignition_3m_confirmation as gs455

        signal = gs455.progression_signal(record)
        return bool(signal.get("active") and signal.get("new_rung") in {"1m", "3m", "5m", "10m", "15m"})
    except Exception:
        return False


def stale_legacy_developing(record: dict, view: dict) -> bool:
    """Identify only the late standalone-ignition presentation case."""
    semantics = view.get("look_now_semantics") or {}
    if not semantics.get("legacy_1m_ignition_demoted"):
        return False
    if semantics.get("bottom_up_compression") or semantics.get("jet_fuel"):
        return False
    age = thirty_second_flip_age(record)
    if age is None or age <= FRESH_30S_ATTENTION_SECONDS:
        return False
    return not fresh_higher_maturation(record)


def tightened_opportunity_state(original, record: dict) -> dict:
    """Add truthful late-arrival context while preserving the canonical state."""
    view = original(record)
    if not stale_legacy_developing(record, view):
        return view

    age = thirty_second_flip_age(record)
    minutes = (age or 0.0) / 60.0
    updated = deepcopy(view)
    provenance = list(updated.get("attention_provenance") or [])
    if _PROVENANCE not in provenance:
        provenance.append(_PROVENANCE)
    updated["attention_provenance"] = provenance
    updated["reason"] = (
        f"LATE CONTINUATION WATCH: the earlier 30s ignition is {minutes:.1f} minutes "
        "old. Keep the runner visible, but do not treat this as fresh Developing urgency."
    )
    updated["next_step"] = (
        "Require a fresh 1m/3m maturation event, constructive reset/retest, VWAP reclaim, "
        "or renewed acceleration before elevating operator urgency again."
    )
    updated["freshness_semantics"] = {
        "late_legacy_ignition": True,
        "thirty_second_flip_age_seconds": age,
        "fresh_attention_limit_seconds": FRESH_30S_ATTENTION_SECONDS,
        "authority": "PRESENTATION_ONLY",
    }
    return updated


def _inherit(wrapper, wrapped) -> None:
    for name, value in getattr(wrapped, "__dict__", {}).items():
        if name.startswith("_gs") and not hasattr(wrapper, name):
            setattr(wrapper, name, value)


def install() -> None:
    """Tighten the late presentation boundary without changing trading authority."""
    from . import gs310_unified_opportunity_state as unified
    from . import gs311_unified_voice as voice
    from . import gs314_state_consistency as consistency
    from . import gs363_operator_attention_hierarchy as hierarchy
    from . import gs462_preflip_ignition_watch as preflip

    # GS462 reads this module global dynamically on every evaluation.
    preflip.RECENT_30S_FLIP_SECONDS = FRESH_30S_ATTENTION_SECONDS

    current = unified.opportunity_state
    if getattr(current, _OWNER_ATTR, False):
        calibrated = current
    else:
        @wraps(current)
        def calibrated(record: dict) -> dict:
            return tightened_opportunity_state(current, record)

        _inherit(calibrated, current)
        calibrated._gs525_fresh_attention_expiry = True
        calibrated._gs525_original = current
        setattr(calibrated, _OWNER_ATTR, True)
        unified.opportunity_state = calibrated

    voice.opportunity_state = calibrated
    consistency.opportunity_state = calibrated
    hierarchy.opportunity_state = calibrated

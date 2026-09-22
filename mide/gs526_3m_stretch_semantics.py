"""GS526: stop calling 3m-stretched runners fresh DEVELOPING setups.

Sept. 22 live validation on GELS exposed an internal operator contradiction. Walter
showed GELS as DEVELOPING while its own GS493 guardrail simultaneously reported price
about 15% above the current bullish 3m SuperTrend line. VWAP was still near, so the
base GS310 state did not consider the move extended.

GS526 lets the already-computed GS493 3m-stretch truth adjudicate only that narrow
presentation case:

* base state is DEVELOPING;
* price is still above/near VWAP;
* 3m SuperTrend is bullish but price is more than 5% above the 3m ST line; and
* no fresh higher-timeframe maturation event is actively re-arming attention.

Such a record presents as CHASE / WAIT with explicit 3m-stretch guidance. A fresh
1m/3m/5m+ maturation event preserves the existing fresh-attention path.

Presentation semantics only. No discovery, market-data request, scoring, Mission Rank,
qualification, participation, expansion, readiness, entry authority, 3m retest
definition, execution, or order behavior changes.
"""
from __future__ import annotations

from copy import deepcopy
from functools import wraps

from . import gs493_3m_st_retest_truth as gs493


MAX_DEVELOPING_3M_ST_GAP_PCT = 5.0
_OWNER_ATTR = "_walter_gs526_3m_stretch_semantics_owner"
_PROVENANCE = "GS526_3M_STRETCH_SEMANTICS"


def fresh_higher_maturation(record: dict) -> bool:
    """Reuse established GS455 fresh-rung truth; add no new signal."""
    try:
        from . import gs455_early_ignition_3m_confirmation as gs455

        signal = gs455.progression_signal(record)
        return bool(
            signal.get("active")
            and signal.get("new_rung") in {"1m", "3m", "5m", "10m", "15m"}
        )
    except Exception:
        return False


def materially_stretched_developing(record: dict, view: dict) -> tuple[bool, dict]:
    """Return whether an ordinary DEVELOPING card is already too far above 3m ST."""
    from . import gs310_unified_opportunity_state as unified

    if str(view.get("state") or "") != unified.DEVELOPING:
        return False, {}

    truth = gs493.three_minute_st_retest_truth(record)
    if truth.get("state") != "NOT_AT_3M_ST_YET":
        return False, truth
    if not truth.get("three_minute_bullish"):
        return False, truth

    try:
        gap = float(truth.get("signed_gap_pct"))
    except (TypeError, ValueError):
        return False, truth

    if gap <= MAX_DEVELOPING_3M_ST_GAP_PCT:
        return False, truth
    if fresh_higher_maturation(record):
        return False, truth
    return True, truth


def tightened_opportunity_state(original, record: dict) -> dict:
    """Convert only stale/extended DEVELOPING semantics to CHASE / WAIT."""
    from . import gs310_unified_opportunity_state as unified

    view = original(record)
    stretched, truth = materially_stretched_developing(record, view)
    if not stretched:
        return view

    updated = deepcopy(view)
    updated["state"] = unified.CHASE_WAIT
    updated["color"] = unified.STATE_COLORS[unified.CHASE_WAIT]

    gap = float(truth["signed_gap_pct"])
    price = truth.get("price")
    st_value = truth.get("three_minute_supertrend")
    updated["reason"] = (
        f"Price is still near VWAP, but it is already {gap:.1f}% above the bullish "
        "3m SuperTrend line. The move is no longer a fresh Developing setup."
    )
    updated["next_step"] = (
        "CHASE / WAIT. Keep the runner visible, but require a constructive reset, "
        "3m SuperTrend retest/reclaim, or a fresh higher-timeframe maturation event "
        "before elevating urgency again."
    )
    provenance = list(updated.get("attention_provenance") or [])
    if _PROVENANCE not in provenance:
        provenance.append(_PROVENANCE)
    updated["attention_provenance"] = provenance
    updated["three_minute_stretch_semantics"] = {
        "gap_pct": gap,
        "price": price,
        "three_minute_supertrend": st_value,
        "max_developing_gap_pct": MAX_DEVELOPING_3M_ST_GAP_PCT,
        "authority": "PRESENTATION_ONLY",
    }
    return updated


def _inherit(wrapper, wrapped) -> None:
    for name, value in getattr(wrapped, "__dict__", {}).items():
        if name.startswith("_gs") and not hasattr(wrapper, name):
            setattr(wrapper, name, value)


def install() -> None:
    """Bind after GS525 at the final trader-facing state boundary."""
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
            return tightened_opportunity_state(current, record)

        _inherit(calibrated, current)
        calibrated._gs526_3m_stretch_semantics = True
        calibrated._gs526_original = current
        setattr(calibrated, _OWNER_ATTR, True)
        unified.opportunity_state = calibrated

    voice.opportunity_state = calibrated
    consistency.opportunity_state = calibrated
    hierarchy.opportunity_state = calibrated

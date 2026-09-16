"""GS463: restore state-first operator priority after the newer attention lifts.

Live validation on 2026-09-16 showed an extended CHASE / WAIT card rendering above
current LOOK NOW cards. That was not a stale-runtime artifact: GS457 deliberately
assigned fresh maturation band 45 while ordinary LOOK NOW remained band 40. The
later GS459/GS462 layers inherited that ordering, so a useful attention-only signal
could outrank a genuinely more actionable state.

GS463 keeps the newer evidence but restores the operator contract:

    WATCH FOR ENTRY > LOOK NOW > attention-only ignition/maturation/trajectory
    > DEVELOPING > ordinary CHASE / WAIT > HALTED/other

Fresh maturation, GS462 EARLY WATCH/JET FUEL, and GS459 price-trajectory ignition
remain useful and may still lift an otherwise ordinary symbol above DEVELOPING, but
they can never render above a real LOOK NOW card. This is presentation ordering only;
no state, qualification, threshold, readiness, alert, execution, or order field is
mutated.
"""
from __future__ import annotations

WATCH_FOR_ENTRY_BAND = 60
LOOK_NOW_BAND = 50
JET_FUEL_BAND = 47
EARLY_WATCH_BAND = 46
FRESH_MATURATION_BAND = 45
TRAJECTORY_BAND = 44
RECENT_CONFIRMATION_BAND = 43
DEVELOPING_BAND = 30
CHASE_WAIT_BAND = 20
OTHER_BAND = 10

_OWNER_ATTR = "_walter_gs463_state_first_operator_order_owner"


def effective_operator_attention_band(record: dict) -> int:
    """Return the final presentation band without rewriting Opportunity State."""
    from . import gs310_unified_opportunity_state as unified
    from . import gs457_maturation_leader_priority as gs457
    from . import gs459_price_trajectory_attention as gs459
    from . import gs462_preflip_ignition_watch as gs462

    state = str(unified.opportunity_state(record).get("state") or "")
    if state == unified.WATCH_FOR_ENTRY:
        return WATCH_FOR_ENTRY_BAND
    if state == unified.LOOK_NOW:
        return LOOK_NOW_BAND

    preflip = gs462.preflip_ignition_watch(record)
    if preflip.get("active"):
        return JET_FUEL_BAND if preflip.get("jet_fuel") else EARLY_WATCH_BAND

    maturation = gs457.maturation_attention(record)
    if maturation.get("fresh_maturation"):
        return FRESH_MATURATION_BAND

    if gs459.trajectory_attention(record).get("active"):
        return TRAJECTORY_BAND

    if maturation.get("sustained_confirmation"):
        return RECENT_CONFIRMATION_BAND

    if state == unified.DEVELOPING:
        return DEVELOPING_BAND
    if state == unified.CHASE_WAIT:
        return CHASE_WAIT_BAND
    return OTHER_BAND


def ordered_state_first_records(records: list[dict], baseline_order=None) -> list[dict]:
    """Apply one final stable state/attention band above the established tie-breaks."""
    rows = list(baseline_order(records) if baseline_order is not None else (records or []))
    # Stable sort preserves every established within-band ordering/tie-breaker.
    rows.sort(key=effective_operator_attention_band, reverse=True)
    return rows


def _inherit(wrapper, wrapped) -> None:
    for name, value in getattr(wrapped, "__dict__", {}).items():
        if name.startswith("_gs") and not hasattr(wrapper, name):
            setattr(wrapper, name, value)


def install() -> None:
    """Bind GS463 outside the current GS462/GS459/GS457 ordering stack."""
    from . import gs369_escalation_priority_order as gs369

    current = gs369.ordered_escalation_records
    if getattr(current, _OWNER_ATTR, False):
        return

    def ordered_escalation_records(records: list[dict]) -> list[dict]:
        return ordered_state_first_records(records, baseline_order=current)

    _inherit(ordered_escalation_records, current)
    ordered_escalation_records._gs463_state_first_operator_order = True
    ordered_escalation_records._gs463_original = current
    setattr(ordered_escalation_records, _OWNER_ATTR, True)
    gs369.ordered_escalation_records = ordered_escalation_records

"""GS528: make ENTRY READY a single canonical executable contract.

Sept. 22 live review exposed a semantic split: Walter's architecture could stamp
candidate_status=Entry Ready merely because a record advanced through Expansion,
while Scanner V2's actual executable truth remained qualified_for_entry=False.

GS528 establishes one vocabulary contract:
- ENTRY READY means and only means qualified_for_entry is True.
- A record that is close but not qualified is SETTING UP, with exact blockers.
- Existing LOOK NOW / CHASE / WAIT / maturation semantics remain intact.
- No qualification predicate, threshold, readiness rule, anti-chase rule, retest rule,
  execution behavior, or order behavior changes.
"""
from __future__ import annotations

from copy import deepcopy
from functools import wraps

_OWNER = "_walter_gs528_canonical_entry_ready_owner"


def _trigger(record: dict) -> dict:
    value = record.get("trigger_diagnostics") or {}
    return value if isinstance(value, dict) else {}


def entry_contract(record: dict) -> dict:
    """Return canonical executable truth plus exact remaining blockers."""
    trigger = _trigger(record)
    structure = record.get("structure_gate") or {}
    checks = [
        check for check in trigger.get("checks") or []
        if isinstance(check, dict)
    ]
    passed_count = sum(bool(check.get("passed")) for check in checks)
    total_count = len(checks)
    structure_passed = bool(structure.get("passed"))
    qualified = bool(record.get("qualified_for_entry") is True)

    blockers = []
    if not structure_passed:
        reasons = structure.get("failed_reasons") or structure.get("reasons") or []
        if reasons:
            blockers.extend(str(reason) for reason in reasons[:2])
        else:
            blockers.append("Structure gate not passed")
    for check in checks:
        if not check.get("passed"):
            blockers.append(
                str(check.get("failed_reason") or check.get("condition") or "Trigger condition not passed")
            )
    blockers = list(dict.fromkeys(blockers))

    legacy_ready = str(record.get("candidate_status") or record.get("status") or "") == "Entry Ready"
    if qualified:
        label = "ENTRY READY"
    elif structure_passed and total_count and passed_count >= max(1, total_count - 1):
        label = f"SETTING UP · {passed_count}/{total_count} TRIGGER LOCKS"
    else:
        label = "SETTING UP"

    return {
        "qualified_for_entry": qualified,
        "label": label,
        "structure_passed": structure_passed,
        "trigger_passed": bool(trigger.get("passed")),
        "passed_trigger_locks": passed_count,
        "total_trigger_locks": total_count,
        "blockers": blockers,
        "legacy_false_entry_ready": bool(legacy_ready and not qualified),
        "authority": "CANONICAL_ENTRY_LABEL_ONLY",
    }



def canonical_candidate_status(record: dict, default: str = "Strengthening") -> str:
    """Return a workflow label that cannot manufacture Entry Ready."""
    if record.get("qualified_for_entry") is True:
        return "Entry Ready"
    existing = str(record.get("candidate_status") or "").strip()
    if existing and existing != "Entry Ready":
        return existing
    return default

def state_with_entry_contract(original, record: dict) -> dict:
    """Expose canonical entry truth without changing executable authority."""
    view = original(record)
    contract = entry_contract(record)
    result = deepcopy(view)
    result["entry_contract"] = contract

    if contract["qualified_for_entry"]:
        prefix = "ENTRY READY: Walter's executable entry contract is satisfied."
        reason = str(result.get("reason") or "").strip()
        if not reason.startswith("ENTRY READY:"):
            result["reason"] = f"{prefix} {reason}".strip()
        return result

    blockers = contract["blockers"]
    blocker_text = blockers[0] if blockers else "Entry qualification is not yet satisfied"
    if contract["legacy_false_entry_ready"]:
        prefix = "SETTING UP · NOT ENTRY READY:"
    else:
        prefix = contract["label"] + ":"
    reason = str(result.get("reason") or "").strip()
    if not reason.startswith("SETTING UP"):
        result["reason"] = f"{prefix} {reason}".strip()
    next_step = str(result.get("next_step") or "").strip()
    exact = f"Entry blocker: {blocker_text}"
    if exact not in next_step:
        result["next_step"] = f"{exact}. {next_step}".strip()
    return result


def _inherit(wrapper, wrapped) -> None:
    for name, value in getattr(wrapped, "__dict__", {}).items():
        if name.startswith("_gs") and not hasattr(wrapper, name):
            setattr(wrapper, name, value)


def install() -> None:
    """Bind at the final Opportunity State boundary."""
    from . import gs310_unified_opportunity_state as unified
    from . import gs311_unified_voice as voice
    from . import gs314_state_consistency as consistency
    from . import gs363_operator_attention_hierarchy as hierarchy

    current = unified.opportunity_state
    if getattr(current, _OWNER, False):
        calibrated = current
    else:
        @wraps(current)
        def calibrated(record: dict) -> dict:
            return state_with_entry_contract(current, record)

        _inherit(calibrated, current)
        calibrated._gs528_canonical_entry_ready = True
        calibrated._gs528_original = current
        setattr(calibrated, _OWNER, True)
        unified.opportunity_state = calibrated

    voice.opportunity_state = calibrated
    consistency.opportunity_state = calibrated
    hierarchy.opportunity_state = calibrated

"""GS529: shadow-calibrate the Entry Ready SuperTrend trigger.

Sept. 22 replay evidence showed that real runners could satisfy broad structure while
never becoming executable because the canonical trigger requires a discrete recent
SuperTrend flip flag. GS529 does NOT change that live rule. It records a shadow
counterfactual: would the setup have become Entry Ready if an established fresh
ordered multi-timeframe maturation event (1m or 3m rung) were allowed to satisfy only
the SuperTrend trigger lock?

This is observational calibration only. It changes no qualification, ranking,
readiness, anti-chase, retest, alert, execution, or order authority.
"""
from __future__ import annotations

from copy import deepcopy


_SHADOW_RUNG_ALLOWLIST = {"1m", "3m"}


def _fresh_progression(record: dict) -> dict:
    try:
        from . import gs455_early_ignition_3m_confirmation as gs455

        signal = gs455.progression_signal(record)
        active = bool(
            signal.get("active") and signal.get("new_rung") in _SHADOW_RUNG_ALLOWLIST
        )
        return {
            "active": active,
            "new_rung": signal.get("new_rung"),
            "highest_rung": signal.get("highest_rung"),
            "fresh_rungs": list(signal.get("fresh_rungs") or []),
            "source": "GS455 progression_signal",
        }
    except Exception as exc:
        return {
            "active": False,
            "new_rung": None,
            "highest_rung": None,
            "fresh_rungs": [],
            "source": "GS455 progression_signal",
            "error": type(exc).__name__,
        }


def shadow_entry_calibration(
    record: dict,
    trigger: dict | None = None,
    structure_gate: dict | None = None,
) -> dict:
    """Compare canonical Entry Ready with a progression-assisted ST shadow."""
    trigger = deepcopy(trigger or record.get("trigger_diagnostics") or {})
    structure_gate = structure_gate or record.get("structure_gate") or {}
    checks = [deepcopy(c) for c in trigger.get("checks") or [] if isinstance(c, dict)]
    progression = _fresh_progression(record)

    canonical_trigger_passed = bool(trigger.get("passed"))
    canonical_entry = bool(structure_gate.get("passed") and canonical_trigger_passed)

    st_shadow_used = False
    for check in checks:
        if check.get("condition") != "supertrend_flip":
            continue
        if not check.get("passed") and progression.get("active"):
            check["passed"] = True
            check["shadow_passed_by"] = "fresh_ordered_maturation"
            check["shadow_rung"] = progression.get("new_rung")
            st_shadow_used = True

    shadow_failed = [
        str(c.get("condition") or "")
        for c in checks
        if not c.get("passed")
    ]
    shadow_trigger_passed = bool(checks) and not shadow_failed
    shadow_entry = bool(structure_gate.get("passed") and shadow_trigger_passed)

    canonical_failed = [
        str(c.get("condition") or "")
        for c in trigger.get("checks") or []
        if isinstance(c, dict) and not c.get("passed")
    ]

    return {
        "authority": "OBSERVATIONAL_ONLY",
        "canonical_entry_ready": canonical_entry,
        "canonical_trigger_passed": canonical_trigger_passed,
        "canonical_failed_conditions": canonical_failed,
        "structure_passed": bool(structure_gate.get("passed")),
        "progression": progression,
        "shadow_st_substitution_used": st_shadow_used,
        "shadow_trigger_passed": shadow_trigger_passed,
        "shadow_failed_conditions": shadow_failed,
        "shadow_entry_ready": shadow_entry,
        "recovered_by_progression": bool(shadow_entry and not canonical_entry),
        "trading_authority_changed": False,
    }

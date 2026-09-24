"""GS529: warm-deploy-safe Replay / Validation facade for Entry Ready shadow calibration.

GS529 remains observational only. Its progression-assisted SuperTrend counterfactual
now lives in authoritative Replay / Validation, while this historical module retains
the mutable rung allowlist and _fresh_progression monkeypatch seam used by regression
tests and calibration work.

A stale warm Replay / Validation generation fails closed: the shadow cannot recover an
entry, and no live qualification, readiness, alert, execution, or order authority is
changed.
"""

from __future__ import annotations


_SHADOW_RUNG_ALLOWLIST = {"1m", "3m"}


def _replay():
    from mide.authorities import replay_validation

    return replay_validation


def _fresh_progression(record: dict) -> dict:
    current = getattr(
        _replay(),
        "entry_shadow_fresh_progression",
        None,
    )
    if callable(current):
        return current(record)
    return {
        "active": False,
        "new_rung": None,
        "highest_rung": None,
        "fresh_rungs": [],
        "source": "Replay / Validation unavailable",
    }


def shadow_entry_calibration(
    record: dict,
    trigger: dict | None = None,
    structure_gate: dict | None = None,
) -> dict:
    current = getattr(
        _replay(),
        "shadow_entry_calibration",
        None,
    )
    if callable(current):
        return current(
            record,
            trigger=trigger,
            structure_gate=structure_gate,
        )

    trigger = (
        trigger
        or record.get("trigger_diagnostics")
        or {}
    )
    structure_gate = (
        structure_gate
        or record.get("structure_gate")
        or {}
    )
    canonical_trigger_passed = bool(
        trigger.get("passed")
    )
    canonical_entry = bool(
        structure_gate.get("passed")
        and canonical_trigger_passed
    )
    canonical_failed = [
        str(check.get("condition") or "")
        for check in trigger.get("checks") or []
        if (
            isinstance(check, dict)
            and not check.get("passed")
        )
    ]
    return {
        "authority": "OBSERVATIONAL_ONLY",
        "canonical_entry_ready": canonical_entry,
        "canonical_trigger_passed": (
            canonical_trigger_passed
        ),
        "canonical_failed_conditions": (
            canonical_failed
        ),
        "structure_passed": bool(
            structure_gate.get("passed")
        ),
        "progression": _fresh_progression(record),
        "shadow_st_substitution_used": False,
        "shadow_trigger_passed": (
            canonical_trigger_passed
        ),
        "shadow_failed_conditions": (
            canonical_failed
        ),
        "shadow_entry_ready": False,
        "recovered_by_progression": False,
        "trading_authority_changed": False,
    }


def __getattr__(name: str):
    try:
        return getattr(_replay(), name)
    except AttributeError:
        raise AttributeError(name) from None


__all__ = [
    "shadow_entry_calibration",
]

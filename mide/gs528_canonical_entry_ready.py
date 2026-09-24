"""Compatibility shim for the canonical Walter Next Entry Authority.

GS528 originally established Walter's executable Entry Ready vocabulary. That
behavior now lives in mide.authorities.entry_authority. This historical module remains
at its validated import/install points, but resolves Entry Authority lazily so a stale
warm Streamlit generation cannot fail merely because newer authority exports are
absent.

Current runtimes receive the exact authoritative callable objects. Stale retained
runtimes fail closed: they cannot manufacture Entry Ready, cannot rewrite Opportunity
State, and installation becomes a no-op. No qualification predicate, threshold,
anti-chase rule, retest rule, execution behavior, or order behavior changes.
"""

from __future__ import annotations


_EXPORTS = {
    "canonical_candidate_status": "canonical_candidate_status",
    "entry_contract": "entry_contract",
    "install": "install",
    "state_with_entry_contract": "state_with_entry_contract",
}


def _entry_authority():
    from mide.authorities import entry_authority

    return entry_authority


def _fallback_candidate_status(record: dict, default: str = "Strengthening") -> str:
    """Fail closed without reviving a stale Entry Ready label."""
    existing = str(record.get("candidate_status") or "").strip()
    if existing and existing != "Entry Ready":
        return existing
    return default


def _fallback_entry_contract(record: dict) -> dict:
    """Return explicitly non-executable truth when the authority export is unavailable."""
    legacy_ready = (
        str(record.get("candidate_status") or record.get("status") or "")
        == "Entry Ready"
    )
    return {
        "qualified_for_entry": False,
        "label": "SETTING UP",
        "structure_passed": False,
        "trigger_passed": False,
        "passed_trigger_locks": 0,
        "total_trigger_locks": 0,
        "blockers": ["Entry Authority unavailable in retained runtime"],
        "legacy_false_entry_ready": bool(legacy_ready),
        "authority": "STALE_ENTRY_AUTHORITY_FALLBACK",
    }


def _fallback_state_with_entry_contract(original, record: dict) -> dict:
    return original(record)


def _noop_install() -> None:
    return None


_FALLBACKS = {
    "canonical_candidate_status": _fallback_candidate_status,
    "entry_contract": _fallback_entry_contract,
    "install": _noop_install,
    "state_with_entry_contract": _fallback_state_with_entry_contract,
}


def __getattr__(name: str):
    target = _EXPORTS.get(name)
    if target is not None:
        value = getattr(_entry_authority(), target, None)
        if callable(value):
            return value
        return _FALLBACKS[name]
    try:
        return getattr(_entry_authority(), name)
    except AttributeError:
        raise AttributeError(name) from None


__all__ = [
    "canonical_candidate_status",
    "entry_contract",
    "install",
    "state_with_entry_contract",
]

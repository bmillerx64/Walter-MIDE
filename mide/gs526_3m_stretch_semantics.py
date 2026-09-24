"""Compatibility shim/facade for Walter Next 3m-stretch semantics.

Thesis / State owns GS526's presentation-only 3m-stretch adjudication. This historical
module preserves the validated helper/install surface while resolving Thesis / State
lazily for warm Streamlit safety. The historical gs493 module seam remains available
for regression monkeypatching and current retest truth.

A stale retained Thesis/State generation fails closed: it does not manufacture
stretch truth, does not rewrite state, and no-ops installation. No qualification,
readiness, execution, or order authority changes.
"""
from __future__ import annotations

from . import gs493_3m_st_retest_truth as gs493


MAX_DEVELOPING_3M_ST_GAP_PCT = 5.0
_OWNER_ATTR = "_walter_gs526_3m_stretch_semantics_owner"
_PROVENANCE = "GS526_3M_STRETCH_SEMANTICS"


def _thesis():
    from mide.authorities import thesis_state

    return thesis_state


def fresh_higher_maturation(record: dict) -> bool:
    current = getattr(_thesis(), "fresh_higher_maturation", None)
    if not callable(current):
        return False
    return bool(current(record))


def materially_stretched_developing(record: dict, view: dict) -> tuple[bool, dict]:
    current = getattr(_thesis(), "materially_stretched_developing", None)
    if not callable(current):
        return False, {}
    return current(record, view)


def tightened_opportunity_state(original, record: dict) -> dict:
    current = getattr(_thesis(), "stretch_adjusted_state", None)
    if not callable(current):
        return original(record)
    return current(original, record)


def install() -> None:
    current = getattr(_thesis(), "install_3m_stretch_semantics", None)
    if callable(current):
        current()


def __getattr__(name: str):
    try:
        return getattr(_thesis(), name)
    except AttributeError:
        raise AttributeError(name) from None


__all__ = [
    "MAX_DEVELOPING_3M_ST_GAP_PCT",
    "fresh_higher_maturation",
    "install",
    "materially_stretched_developing",
    "tightened_opportunity_state",
]

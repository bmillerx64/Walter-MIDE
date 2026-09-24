"""Compatibility facade for Walter Next late-attention freshness semantics.

Thesis / State owns GS525's five-minute 30s attention freshness and late-continuation
presentation semantics. This historical module preserves the validated callable and
install surface while resolving the authority lazily for warm Streamlit safety.

A stale retained Thesis/State generation fails closed: it cannot invent fresh
maturation, does not rewrite state, and no-ops installation. No qualification,
readiness, execution, or order authority changes.
"""
from __future__ import annotations


FRESH_30S_ATTENTION_SECONDS = 5 * 60.0
_OWNER_ATTR = "_walter_gs525_fresh_attention_expiry_owner"
_PROVENANCE = "GS525_LATE_IGNITION_CONTEXT"


def _thesis():
    from mide.authorities import thesis_state

    return thesis_state


def thirty_second_flip_age(record: dict) -> float | None:
    current = getattr(_thesis(), "thirty_second_flip_age", None)
    if not callable(current):
        return None
    return current(record)


def fresh_higher_maturation(record: dict) -> bool:
    current = getattr(_thesis(), "fresh_higher_maturation", None)
    if not callable(current):
        return False
    return bool(current(record))


def stale_legacy_developing(record: dict, view: dict) -> bool:
    current = getattr(_thesis(), "stale_legacy_developing", None)
    if not callable(current):
        return False
    return bool(current(record, view))


def tightened_opportunity_state(original, record: dict) -> dict:
    current = getattr(_thesis(), "tighten_late_attention_state", None)
    if not callable(current):
        return original(record)
    return current(original, record)


def install() -> None:
    current = getattr(_thesis(), "install_fresh_attention_expiry", None)
    if callable(current):
        current()


def __getattr__(name: str):
    try:
        return getattr(_thesis(), name)
    except AttributeError:
        raise AttributeError(name) from None


__all__ = [
    "FRESH_30S_ATTENTION_SECONDS",
    "fresh_higher_maturation",
    "install",
    "stale_legacy_developing",
    "thirty_second_flip_age",
    "tightened_opportunity_state",
]

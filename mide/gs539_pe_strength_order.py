"""Compatibility facade for P/E Strength presentation ordering.

Presentation + Audio owns GS539's visible Participation/Expansion strength meaning,
state annotation, and final operator-order stage. This historical module preserves the
validated callable/install surface while resolving the authority lazily for warm
Streamlit safety.

A stale retained Presentation generation fails closed: missing strength evidence
returns None, incoming baseline order is preserved, state is left unchanged, and
installation becomes a no-op. No qualification, readiness, execution, or order
authority changes.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable


def _presentation():
    from mide.authorities import presentation_audio

    return presentation_audio


def participation_value(record: dict) -> float | None:
    current = getattr(_presentation(), "participation_value", None)
    if not callable(current):
        return None
    return current(record)


def expansion_value(record: dict) -> float | None:
    current = getattr(_presentation(), "expansion_value", None)
    if not callable(current):
        return None
    return current(record)


def pe_strength_score(record: dict) -> float | None:
    current = getattr(_presentation(), "pe_strength_score", None)
    if not callable(current):
        return None
    return current(record)


def ordered_pe_strength_records(
    records: Iterable[dict],
    *,
    baseline_order: Callable[[list[dict]], list[dict]] | None = None,
) -> list[dict]:
    current = getattr(_presentation(), "ordered_pe_strength_records", None)
    if not callable(current):
        rows = list(records or [])
        return list(
            baseline_order(rows)
            if baseline_order is not None
            else rows
        )
    return current(
        records,
        baseline_order=baseline_order,
    )


def state_with_pe_strength(original, record: dict) -> dict:
    current = getattr(_presentation(), "state_with_pe_strength", None)
    if not callable(current):
        return original(record)
    return current(original, record)


def install() -> None:
    current = getattr(_presentation(), "install_pe_strength_order", None)
    if callable(current):
        current()


def __getattr__(name: str):
    try:
        return getattr(_presentation(), name)
    except AttributeError:
        raise AttributeError(name) from None


__all__ = [
    "participation_value",
    "expansion_value",
    "pe_strength_score",
    "ordered_pe_strength_records",
    "state_with_pe_strength",
    "install",
]

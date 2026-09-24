"""Compatibility facade for fresh-maturation operator priority.

Presentation + Audio owns GS517's fresh-maturation event and final operator-order
semantics. This historical module preserves the validated callable/install surface
while resolving the authority lazily so a stale warm Streamlit generation cannot fail
because a newer Presentation + Audio export is absent.

The fallback path is intentionally inert: stale generations preserve their incoming
baseline order and do not manufacture fresh maturation. No ranking calculation,
qualification, readiness, alert, execution, or order authority changes.
"""
from __future__ import annotations

from collections.abc import Callable, Iterable


def _presentation():
    from mide.authorities import presentation_audio

    return presentation_audio


def fresh_maturation_event(record: dict) -> bool:
    current = getattr(
        _presentation(),
        "fresh_maturation_event",
        None,
    )
    if not callable(current):
        return False
    return bool(current(record))


def ordered_fresh_event_records(
    records: Iterable[dict],
    *,
    baseline_order: Callable[[list[dict]], list[dict]] | None = None,
) -> list[dict]:
    current = getattr(
        _presentation(),
        "ordered_fresh_event_records",
        None,
    )
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


def install() -> None:
    current = getattr(
        _presentation(),
        "activate_operator_order_stage",
        None,
    )
    if callable(current):
        current("fresh_event")


def __getattr__(name: str):
    try:
        return getattr(_presentation(), name)
    except AttributeError:
        raise AttributeError(name) from None


__all__ = [
    "fresh_maturation_event",
    "ordered_fresh_event_records",
    "install",
]

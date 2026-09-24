"""Warm-deploy-safe facade for Mission-Rank-aware operator ordering.

Presentation + Audio owns GS497 ordering semantics. This historical module preserves
the validated callable/install surface while resolving the authority lazily for warm
Streamlit safety.

No ranking calculation or trading authority changes.
"""
from __future__ import annotations

from collections.abc import Callable, Iterable


def _presentation():
    from mide.authorities import presentation_audio

    return presentation_audio


def current_mission_rank(
    record: dict,
) -> int | None:
    current = getattr(
        _presentation(),
        "current_mission_rank",
        None,
    )
    if not callable(current):
        return None
    return current(record)


def ordered_rank_aware_records(
    records: Iterable[dict],
    *,
    baseline_order: Callable[
        [list[dict]],
        list[dict],
    ]
    | None = None,
) -> list[dict]:
    current = getattr(
        _presentation(),
        "ordered_rank_aware_records",
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
        current("rank_aware")


def __getattr__(name: str):
    try:
        return getattr(_presentation(), name)
    except AttributeError:
        raise AttributeError(name) from None


__all__ = [
    "current_mission_rank",
    "ordered_rank_aware_records",
    "install",
]

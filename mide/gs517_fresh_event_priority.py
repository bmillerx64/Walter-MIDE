"""Compatibility facade for fresh-maturation operator priority."""

from __future__ import annotations

from collections.abc import Callable, Iterable

from .authorities import presentation_audio as _presentation


def fresh_maturation_event(record: dict) -> bool:
    return _presentation.fresh_maturation_event(record)


def ordered_fresh_event_records(
    records: Iterable[dict],
    *,
    baseline_order: Callable[[list[dict]], list[dict]] | None = None,
) -> list[dict]:
    return _presentation.ordered_fresh_event_records(
        records,
        baseline_order=baseline_order,
    )


def install() -> None:
    _presentation.activate_operator_order_stage("fresh_event")


__all__ = ["fresh_maturation_event", "ordered_fresh_event_records", "install"]

"""Compatibility facade for Mission-Rank-aware operator ordering."""

from __future__ import annotations

from collections.abc import Callable, Iterable

from .authorities import presentation_audio as _presentation


def current_mission_rank(record: dict) -> int | None:
    return _presentation.current_mission_rank(record)


def ordered_rank_aware_records(
    records: Iterable[dict],
    *,
    baseline_order: Callable[[list[dict]], list[dict]] | None = None,
) -> list[dict]:
    return _presentation.ordered_rank_aware_records(
        records,
        baseline_order=baseline_order,
    )


def install() -> None:
    _presentation.activate_operator_order_stage("rank_aware")


__all__ = ["current_mission_rank", "ordered_rank_aware_records", "install"]

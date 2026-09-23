"""Compatibility facade for P/E Strength presentation ordering.

Visible Participation/Expansion strength meaning and the final ordering stage now live
in mide.authorities.presentation_audio.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable

from .authorities import presentation_audio as _presentation


def participation_value(record: dict) -> float | None:
    return _presentation.participation_value(record)


def expansion_value(record: dict) -> float | None:
    return _presentation.expansion_value(record)


def pe_strength_score(record: dict) -> float | None:
    return _presentation.pe_strength_score(record)


def ordered_pe_strength_records(
    records: Iterable[dict],
    *,
    baseline_order: Callable[[list[dict]], list[dict]] | None = None,
) -> list[dict]:
    return _presentation.ordered_pe_strength_records(
        records,
        baseline_order=baseline_order,
    )


def state_with_pe_strength(original, record: dict) -> dict:
    return _presentation.state_with_pe_strength(original, record)


def install() -> None:
    _presentation.install_pe_strength_order()


__all__ = [
    "participation_value",
    "expansion_value",
    "pe_strength_score",
    "ordered_pe_strength_records",
    "state_with_pe_strength",
    "install",
]

"""Compatibility facade for Walter Next base extreme-mover presentation.

The base extraordinary-event description, selector, markup, action-first render
behavior, diagnostics-sidebar routing, and voice-transport sidebar placement now live
in mide.authorities.presentation_audio.

This historical module remains at the validated GS333 install/import position so
later GS393/GS465/GS495 compatibility installers can still refine its public
callables in the same order.
"""

from __future__ import annotations

from collections.abc import Iterable

from .authorities import presentation_audio as _presentation


EXTREME_MOVER_PCT = _presentation.EXTREME_MOVER_PCT


def extreme_market_event(record: dict) -> dict | None:
    return _presentation.base_extreme_market_event(record)


def prioritized_extreme_event(
    records: Iterable[dict],
) -> tuple[dict | None, dict | None]:
    return _presentation.prioritized_extreme_event(records)


def extreme_event_markup(event: dict) -> str:
    return _presentation.extreme_event_markup(event)


def install() -> None:
    _presentation.install_base_extreme_presentation()


__all__ = [
    "EXTREME_MOVER_PCT",
    "extreme_market_event",
    "prioritized_extreme_event",
    "extreme_event_markup",
    "install",
]

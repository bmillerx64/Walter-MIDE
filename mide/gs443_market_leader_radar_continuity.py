"""Compatibility facade for Walter Next market-leader continuity.

The GS443 watch-only leader selection, markup, and render wrapper now live in
mide.authorities.presentation_audio. This historical module remains at the validated
GS443 install/import position used by GS442 cold and warm paths.
"""

from __future__ import annotations

from collections.abc import Iterable

from .authorities import presentation_audio as _presentation


MAJOR_MOVER_PCT = _presentation.MAJOR_MOVER_PCT
MIN_DOLLAR_VOLUME = _presentation.MIN_DOLLAR_VOLUME
LEADER_DOMINANCE = _presentation.LEADER_DOMINANCE


def market_leader_candidate(
    records: Iterable[dict],
    *,
    mission: dict | None = None,
) -> tuple[dict | None, dict | None]:
    return _presentation.market_leader_candidate(records, mission=mission)


def market_leader_markup(event: dict) -> str:
    return _presentation.market_leader_markup(event)


def install() -> None:
    _presentation.install_market_leader_continuity()


__all__ = [
    "MAJOR_MOVER_PCT",
    "MIN_DOLLAR_VOLUME",
    "LEADER_DOMINANCE",
    "market_leader_candidate",
    "market_leader_markup",
    "install",
]

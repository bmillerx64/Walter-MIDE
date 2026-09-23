"""Compatibility facade for Walter Next extreme-mover anti-chase semantics.

The GS495 <=2% VWAP working-zone qualifier now lives in
mide.authorities.presentation_audio. This historical module remains at the validated
install/import position.
"""

from __future__ import annotations

from .authorities import presentation_audio as _presentation

ANTI_CHASE_VWAP_DISTANCE_PCT = _presentation.ANTI_CHASE_VWAP_DISTANCE_PCT


def truthful_extreme_market_event(original, record: dict) -> dict | None:
    return _presentation.truthful_extreme_market_event(original, record)


def install() -> None:
    _presentation.activate_extreme_event_stage("anti_chase")


__all__ = [
    "ANTI_CHASE_VWAP_DISTANCE_PCT",
    "truthful_extreme_market_event",
    "install",
]

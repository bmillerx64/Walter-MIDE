"""Warm-deploy-safe facade for Walter Next extreme-mover anti-chase semantics.

Presentation + Audio owns GS495's <=2% VWAP working-zone qualifier. This historical
module remains at the validated install/import position but resolves the authority
lazily so a stale warm Streamlit generation cannot fail merely because a newer
presentation export is absent.

No trading authority changes.
"""
from __future__ import annotations


ANTI_CHASE_VWAP_DISTANCE_PCT = 2.0


def _presentation():
    from mide.authorities import presentation_audio

    return presentation_audio


def truthful_extreme_market_event(
    original,
    record: dict,
) -> dict | None:
    current = getattr(
        _presentation(),
        "truthful_extreme_market_event",
        None,
    )
    if not callable(current):
        return original(record)
    return current(original, record)


def install() -> None:
    current = getattr(
        _presentation(),
        "activate_extreme_event_stage",
        None,
    )
    if callable(current):
        current("anti_chase")


def __getattr__(name: str):
    try:
        return getattr(_presentation(), name)
    except AttributeError:
        raise AttributeError(name) from None


__all__ = [
    "ANTI_CHASE_VWAP_DISTANCE_PCT",
    "truthful_extreme_market_event",
    "install",
]

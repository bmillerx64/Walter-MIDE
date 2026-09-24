"""Compatibility facade for visible browser alert-audio health.

Presentation + Audio owns GS516's always-visible parent-window AudioContext health
markup and sidebar renderer. This historical module remains the app/startup import
surface and resolves the authority lazily for warm Streamlit safety.

GS520 still anchors the control beside sidebar audio settings; GS524's audible
two-strike health-check bell remains unchanged. Presentation/transport only: no alert
semantics, tiers, phrases, scanning, market data, scoring, qualification, ranking,
readiness, execution or orders change.
"""
from __future__ import annotations


_OWNER = "_walter_gs516_visible_alert_audio_health"


def _presentation():
    from mide.authorities import presentation_audio

    return presentation_audio


def alert_audio_health_markup() -> str:
    current = getattr(
        _presentation(),
        "alert_audio_health_markup",
        None,
    )
    return str(current()) if callable(current) else ""


def render_sidebar_audio_health(st_module) -> None:
    """Preserve the historical app import while delegating presentation ownership."""
    current = getattr(
        _presentation(),
        "render_sidebar_audio_health",
        None,
    )
    if callable(current):
        current(st_module)


def install() -> None:
    """Compatibility hook; GS520 renders GS516 directly beside sidebar audio controls."""
    return None


def __getattr__(name: str):
    try:
        return getattr(_presentation(), name)
    except AttributeError:
        raise AttributeError(name) from None


__all__ = [
    "alert_audio_health_markup",
    "render_sidebar_audio_health",
    "install",
]

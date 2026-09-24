"""Compatibility facade for GS504 categorical browser-action audio.

Presentation + Audio owns the final tier-2 harmonic bell and tier-3 sustained siren
synthesis. This historical module remains at the validated GS441 install position and
resolves the authority lazily for warm Streamlit safety.

Tier classification, GS367 broker selection, scan-token aggregation, speech, dedupe,
alert truth, and all trading authority remain unchanged.
"""
from __future__ import annotations


_OWNER = "_walter_gs504_distinct_attention_alarm"
_MARKER = "GS504: categorical action audio"


def _presentation():
    from mide.authorities import presentation_audio

    return presentation_audio


def distinct_attention_markup(
    markup: str,
) -> str:
    current = getattr(
        _presentation(),
        "distinct_attention_markup",
        None,
    )
    if not callable(current):
        return str(markup or "")
    return current(markup)


def _inherit(wrapper, wrapped) -> None:
    current = getattr(
        _presentation(),
        "_inherit_audio_wrapper",
        None,
    )
    if callable(current):
        current(wrapper, wrapped)


def install() -> None:
    current = getattr(
        _presentation(),
        "install_distinct_attention_audio",
        None,
    )
    if callable(current):
        current()


def __getattr__(name: str):
    try:
        return getattr(_presentation(), name)
    except AttributeError:
        raise AttributeError(name) from None


__all__ = [
    "distinct_attention_markup",
    "install",
]

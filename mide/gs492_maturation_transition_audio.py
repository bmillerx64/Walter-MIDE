"""Compatibility facade for Walter Next runner-maturation audio.

Maturation transition meaning, phrasing, and wrapper installation now live in
mide.authorities.presentation_audio. This historical module remains at the validated
GS492 install/import position.
"""

from __future__ import annotations


def _gate_passed(record: dict, name: str) -> bool:
    from .authorities import presentation_audio
    return presentation_audio._maturation_gate_passed(record, name)


def maturation_transition(record: dict) -> dict:
    from .authorities import presentation_audio
    return presentation_audio.maturation_transition(record)


def maturation_audio_phrase(records: list[dict]) -> str:
    from .authorities import presentation_audio
    return presentation_audio.maturation_audio_phrase(records)


def install() -> None:
    from .authorities import presentation_audio
    presentation_audio.install_maturation_transition_audio()


def __getattr__(name: str):
    if name == "FRESH_3M_SECONDS":
        from .authorities import presentation_audio
        return presentation_audio.FRESH_3M_SECONDS
    raise AttributeError(name)


__all__ = ["maturation_transition", "maturation_audio_phrase", "install"]

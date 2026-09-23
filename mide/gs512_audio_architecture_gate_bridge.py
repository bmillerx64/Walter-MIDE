"""Compatibility facade for Architecture-v1 audio gate truth.

The authoritative audio gate resolver and historical GS512 activation point now live
in mide.authorities.presentation_audio.
"""

from __future__ import annotations

AUTHORITY = "AUDIO_COMPATIBILITY_ONLY"


def authoritative_gate_passed(record: dict, name: str) -> bool:
    from .authorities import presentation_audio
    return presentation_audio.authoritative_gate_passed(record, name)


def install() -> None:
    from .authorities import presentation_audio
    presentation_audio.install_audio_architecture_gate_bridge()


__all__ = ["AUTHORITY", "authoritative_gate_passed", "install"]

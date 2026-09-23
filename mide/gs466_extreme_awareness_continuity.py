"""Compatibility facade for current-extreme awareness continuity.

The GS466 awareness-only stale-source-bar exception now lives in
mide.authorities.presentation_audio. The historical install point is preserved.
"""

from __future__ import annotations

from .authorities import presentation_audio as _presentation


def extreme_awareness_continuity(record: dict, *, base_reason: str) -> bool:
    return _presentation.extreme_awareness_continuity(
        record,
        base_reason=base_reason,
    )


def install() -> None:
    _presentation.install_extreme_awareness_continuity()


__all__ = ["extreme_awareness_continuity", "install"]

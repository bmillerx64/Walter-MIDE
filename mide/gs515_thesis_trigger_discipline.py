"""Compatibility facade for authoritative retest thesis/trigger discipline.

The THESIS VALIDATED / TRIGGER NOT EARNED presentation contract now lives in
mide.authorities.thesis_state. The historical GS515 install point remains only to
preserve the validated wrapper order.

Authority contract retained: PRESENTATION_DISCIPLINE_ONLY.
"""

from __future__ import annotations

AUTHORITY = "PRESENTATION_DISCIPLINE_ONLY"


def emphasize_discipline(view: dict) -> dict:
    from .authorities import thesis_state
    return thesis_state.emphasize_discipline(view)


def install() -> None:
    from .authorities import thesis_state
    thesis_state.install_retest_discipline()


__all__ = ["AUTHORITY", "emphasize_discipline", "install"]

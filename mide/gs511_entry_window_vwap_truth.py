"""GS511: historical compatibility facade for Entry Window VWAP truth.

Phase 22 moves this display/feed correction into Walter Next's authoritative
Presentation + Audio component. GS511 remains at its historical startup/import point.

The preserved contract is presentation-only: Entry Window Open remains valid only
above and within 2% of VWAP; +2% to +5% degrades to Watch Closely when trend remains
supportive; >5% preserves Too Extended; below-VWAP records cannot present an open
entry window. Scanner qualification, ranking, evidence, execution, and orders remain
unchanged.
"""
from __future__ import annotations

from mide.authorities import presentation_audio as _presentation


_OWNER = _presentation._ENTRY_WINDOW_VWAP_OWNER
NEAR_VWAP_MAX_PCT = _presentation.ENTRY_WINDOW_NEAR_VWAP_MAX_PCT

_number = _presentation._entry_window_number
_near_vwap = _presentation.entry_window_near_vwap


def install() -> None:
    """Install GS511 through authoritative Presentation + Audio ownership."""
    _presentation.install_entry_window_vwap_truth()


def __getattr__(name: str):
    try:
        return getattr(_presentation, name)
    except AttributeError:
        raise AttributeError(name) from None


__all__ = [
    "NEAR_VWAP_MAX_PCT",
    "install",
]

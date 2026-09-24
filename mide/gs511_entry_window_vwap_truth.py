"""Compatibility facade for Entry Window VWAP presentation truth.

Presentation + Audio owns GS511's display/feed correction. This historical module
remains at its validated startup/import point but resolves the authority lazily so a
stale warm Streamlit generation cannot fail because a newer presentation export is
absent.

The preserved contract is presentation-only: Entry Window Open remains valid only
above and within 2% of VWAP; +2% to +5% degrades to Watch Closely when trend remains
supportive; >5% preserves Too Extended; below-VWAP records cannot present an open
entry window. Scanner qualification, ranking, evidence, execution and orders remain
unchanged.
"""
from __future__ import annotations


_EXPORTS = {
    "_OWNER": "_ENTRY_WINDOW_VWAP_OWNER",
    "NEAR_VWAP_MAX_PCT": "ENTRY_WINDOW_NEAR_VWAP_MAX_PCT",
    "_number": "_entry_window_number",
    "_near_vwap": "entry_window_near_vwap",
}


def _presentation():
    from mide.authorities import presentation_audio

    return presentation_audio


def install() -> None:
    """Install GS511 through authoritative Presentation + Audio ownership."""
    current = getattr(
        _presentation(),
        "install_entry_window_vwap_truth",
        None,
    )
    if callable(current):
        current()


def __getattr__(name: str):
    target = _EXPORTS.get(name)
    if target is not None:
        try:
            return getattr(_presentation(), target)
        except AttributeError:
            if name == "NEAR_VWAP_MAX_PCT":
                return 2.0
            raise AttributeError(name) from None
    try:
        return getattr(_presentation(), name)
    except AttributeError:
        raise AttributeError(name) from None


__all__ = [
    "NEAR_VWAP_MAX_PCT",
    "install",
]

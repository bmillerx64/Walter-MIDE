"""GS541: preload current-attention provenance at the hard Streamlit app boundary.

A warm Streamlit deployment can retain older MIDE modules while app.py is re-executed.
GS376 evaluates reclaim-watch state during rendering and historically imported GS309
lazily inside that hot path. Live evidence on 2026-09-24 showed that a concurrent
module import could then form a lock inversion through webull_live -> mide.startup.

This module performs no evaluation and changes no trading semantics. It only makes
GS309 resident before scan/render work starts, so later imports are cache lookups.
"""

from __future__ import annotations


def install() -> None:
    """Preload GS309 without invoking discovery, scanning, or provider work."""
    from . import gs309_current_attention_mission as _gs309  # noqa: F401


__all__ = ["install"]

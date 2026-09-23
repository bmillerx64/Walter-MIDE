"""Compatibility shim for Walter Next freshness semantics owned by Thesis / State."""

from __future__ import annotations

from .authorities.thesis_state import (
    _COMPRESSION_PROVENANCE as _PROVENANCE,
    _FRESH_LOOK_NOW_OWNER_ATTR as _OWNER_ATTR,
    _compression_owned,
    fresh_look_now_state,
    install_fresh_look_now_expiry as install,
)

__all__ = ["fresh_look_now_state", "install"]

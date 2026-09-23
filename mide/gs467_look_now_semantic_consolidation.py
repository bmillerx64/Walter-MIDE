"""Compatibility shim for Walter Next's authoritative LOOK NOW semantics.

GS467 originally adjudicated legacy standalone 1m ignition against stronger bottom-up
structure. That meaning now lives in mide.authorities.thesis_state. This module
remains at the historical installer/import path so the validated wrapper order is
unchanged while Thesis / State consolidation continues.
"""

from __future__ import annotations

from .authorities.thesis_state import (
    _LOOK_NOW_OWNER_ATTR,
    _LOOK_NOW_PROVENANCE as _PROVENANCE,
    bottom_up_urgency,
    consolidated_look_now,
    install_look_now_semantics as install,
    legacy_1m_ignition_look_now,
)

__all__ = [
    "bottom_up_urgency",
    "consolidated_look_now",
    "install",
    "legacy_1m_ignition_look_now",
]

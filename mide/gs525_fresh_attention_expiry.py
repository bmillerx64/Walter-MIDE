"""Compatibility shim for Walter Next late-attention freshness semantics."""

from __future__ import annotations

from .authorities.thesis_state import (
    FRESH_30S_ATTENTION_SECONDS,
    _FRESH_ATTENTION_OWNER_ATTR as _OWNER_ATTR,
    _FRESH_ATTENTION_PROVENANCE as _PROVENANCE,
    fresh_higher_maturation,
    install_fresh_attention_expiry as install,
    stale_legacy_developing,
    thirty_second_flip_age,
    tighten_late_attention_state as tightened_opportunity_state,
)

__all__ = [
    "FRESH_30S_ATTENTION_SECONDS",
    "fresh_higher_maturation",
    "install",
    "stale_legacy_developing",
    "thirty_second_flip_age",
    "tightened_opportunity_state",
]

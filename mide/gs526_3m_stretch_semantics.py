"""Compatibility shim for Walter Next 3m-stretch semantics owned by Thesis / State."""

from __future__ import annotations

from . import gs493_3m_st_retest_truth as gs493
from .authorities.thesis_state import (
    MAX_DEVELOPING_3M_ST_GAP_PCT,
    _STRETCH_OWNER_ATTR as _OWNER_ATTR,
    _STRETCH_PROVENANCE as _PROVENANCE,
    fresh_higher_maturation,
    install_3m_stretch_semantics as install,
    materially_stretched_developing,
    stretch_adjusted_state as tightened_opportunity_state,
)

__all__ = [
    "MAX_DEVELOPING_3M_ST_GAP_PCT",
    "fresh_higher_maturation",
    "install",
    "materially_stretched_developing",
    "tightened_opportunity_state",
]

"""Compatibility shim for Walter Next's authoritative numeric VWAP truth.

GS468 originally established the hard trader-facing veto for contradictory numeric
price/VWAP evidence. That meaning now lives in mide.authorities.thesis_state. This
module remains at the historical installer/import path so the validated wrapper order
is unchanged while the broader Thesis / State chain is consolidated.
"""

from __future__ import annotations

from .authorities.thesis_state import (
    _VWAP_TRUTH_OWNER_ATTR as _OWNER_ATTR,
    _VWAP_TRUTH_PROVENANCE as _PROVENANCE,
    _finite,
    _numeric_below_record,
    _vwap_pair as _pair,
    current_vwap_truth,
    install_vwap_truth as install,
    vwap_truth_state,
)

__all__ = [
    "current_vwap_truth",
    "install",
    "vwap_truth_state",
]

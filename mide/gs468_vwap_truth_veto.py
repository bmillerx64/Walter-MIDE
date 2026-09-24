"""Compatibility shim for Walter Next's authoritative numeric VWAP truth.

GS468's meaning lives in Thesis / State. Phase 37 resolves its historical exports
lazily through module attribute resolution so current runtimes receive the exact
authoritative function objects while stale warm Streamlit generations can safely
no-op the historical installer if that newer authority export is not present.

This remains a presentation-truth veto only. It adds no data request and changes no
indicator, score, qualification, readiness, alert, execution, or order authority.
"""
from __future__ import annotations


_OWNER_ATTR = "_walter_gs468_vwap_truth_veto_owner"
_PROVENANCE = "GS468_NUMERIC_VWAP_VETO"

_EXPORTS = {
    "_finite": "_finite",
    "_pair": "_vwap_pair",
    "current_vwap_truth": "current_vwap_truth",
    "_numeric_below_record": "_numeric_below_record",
    "vwap_truth_state": "vwap_truth_state",
    "install": "install_vwap_truth",
}


def _thesis():
    from mide.authorities import thesis_state

    return thesis_state


def _noop_install() -> None:
    return None


def __getattr__(name: str):
    target = _EXPORTS.get(name)
    if target is not None:
        value = getattr(_thesis(), target, None)
        if callable(value):
            return value
        if name == "install":
            return _noop_install
        raise AttributeError(name)
    try:
        return getattr(_thesis(), name)
    except AttributeError:
        raise AttributeError(name) from None


__all__ = [
    "current_vwap_truth",
    "install",
    "vwap_truth_state",
]

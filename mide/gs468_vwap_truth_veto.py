"""Compatibility shim for Walter Next's authoritative numeric VWAP truth.

GS468's numeric VWAP presentation veto lives in Thesis / State. Phase 37 preserves
the historical helper/install surface while resolving Thesis / State lazily for warm
Streamlit safety.

This remains a presentation-truth veto only. It adds no data request and changes no
indicator, score, qualification, readiness, alert, execution, or order authority.
"""
from __future__ import annotations

from typing import Any


_OWNER_ATTR = "_walter_gs468_vwap_truth_veto_owner"
_PROVENANCE = "GS468_NUMERIC_VWAP_VETO"


def _thesis():
    from mide.authorities import thesis_state

    return thesis_state


def _finite(value: Any) -> float | None:
    current = getattr(_thesis(), "_finite", None)
    if not callable(current):
        raise RuntimeError(
            "Current Thesis / State generation does not yet expose GS468"
        )
    return current(value)


def _pair(close: Any, vwap: Any, source: str) -> dict:
    current = getattr(_thesis(), "_vwap_pair", None)
    if not callable(current):
        raise RuntimeError(
            "Current Thesis / State generation does not yet expose GS468"
        )
    return current(close, vwap, source)


def current_vwap_truth(record: dict) -> dict:
    current = getattr(_thesis(), "current_vwap_truth", None)
    if not callable(current):
        raise RuntimeError(
            "Current Thesis / State generation does not yet expose GS468"
        )
    return current(record)


def _numeric_below_record(record: dict, truth: dict) -> dict:
    current = getattr(
        _thesis(),
        "_numeric_below_record",
        None,
    )
    if not callable(current):
        raise RuntimeError(
            "Current Thesis / State generation does not yet expose GS468"
        )
    return current(record, truth)


def vwap_truth_state(original, record: dict) -> dict:
    current = getattr(_thesis(), "vwap_truth_state", None)
    if not callable(current):
        raise RuntimeError(
            "Current Thesis / State generation does not yet expose GS468"
        )
    return current(original, record)


def install() -> None:
    current = getattr(_thesis(), "install_vwap_truth", None)
    if callable(current):
        current()


def __getattr__(name: str):
    try:
        return getattr(_thesis(), name)
    except AttributeError:
        raise AttributeError(name) from None


__all__ = [
    "current_vwap_truth",
    "install",
    "vwap_truth_state",
]

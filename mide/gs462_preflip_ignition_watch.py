"""GS462: warm-deploy-safe facade for pre-flip ignition attention.

Phase 34 moves GS462's presentation-only implementation into the authoritative
Presentation + Audio component. The historical module remains the compatibility seam
used by GS463/GS465/GS467/GS493/GS514/GS525/GS527 and the regression suite.

The three public calibration constants intentionally remain here. In particular,
GS525 tightens RECENT_30S_FLIP_SECONDS dynamically during late-runtime installation;
Presentation + Audio reads these facade values at evaluation time so that validated
mutation seam remains intact.

The facade resolves its authority lazily. A stale warm Streamlit generation that does
not yet expose Phase 34 installers safely no-ops install() instead of failing startup.

No provider request, indicator pass, opportunity-state rewrite, qualification,
readiness, execution, order, or new audio behavior is introduced.
"""
from __future__ import annotations

from typing import Any


NEAR_ST_LINE_PCT = 2.0
RECENT_30S_FLIP_SECONDS = 10 * 60.0
PRE_FLIP_ATTENTION_BAND = 39
_PROVENANCE = "PRE_FLIP_ST_IGNITION_WATCH"
_ORDER_OWNER_ATTR = "_walter_gs462_preflip_ignition_watch_owner"


def _presentation():
    from mide.authorities import presentation_audio

    return presentation_audio


def _number(value: Any) -> float | None:
    current = getattr(_presentation(), "preflip_number", None)
    if callable(current):
        return current(value)
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _gap_pct(
    close: float | None,
    st_value: float | None,
) -> float | None:
    current = getattr(_presentation(), "preflip_gap_pct", None)
    if callable(current):
        return current(close, st_value)
    close = _number(close)
    st_value = _number(st_value)
    if close in (None, 0) or st_value is None:
        return None
    return abs(st_value - close) / close * 100.0


def _timeframe_detail(record: dict, label: str) -> dict:
    current = getattr(
        _presentation(),
        "preflip_timeframe_detail",
        None,
    )
    if not callable(current):
        raise RuntimeError(
            "Current Presentation + Audio generation "
            "does not yet expose GS462"
        )
    return current(record, label)


def preflip_ignition_watch(record: dict) -> dict:
    current = getattr(
        _presentation(),
        "preflip_ignition_watch",
        None,
    )
    if not callable(current):
        raise RuntimeError(
            "Current Presentation + Audio generation "
            "does not yet expose GS462"
        )
    return current(record)


def _tf_phrase(label: str, detail: dict) -> str:
    current = getattr(
        _presentation(),
        "preflip_tf_phrase",
        None,
    )
    if not callable(current):
        raise RuntimeError(
            "Current Presentation + Audio generation "
            "does not yet expose GS462"
        )
    return current(label, detail)


def _state_with_preflip(original, record: dict) -> dict:
    current = getattr(
        _presentation(),
        "state_with_preflip",
        None,
    )
    if not callable(current):
        raise RuntimeError(
            "Current Presentation + Audio generation "
            "does not yet expose GS462"
        )
    return current(original, record)


def effective_attention_band(record: dict) -> int:
    current = getattr(
        _presentation(),
        "effective_preflip_attention_band",
        None,
    )
    if not callable(current):
        raise RuntimeError(
            "Current Presentation + Audio generation "
            "does not yet expose GS462"
        )
    return current(record)


def ordered_preflip_records(
    records: list[dict],
    baseline_order=None,
) -> list[dict]:
    current = getattr(
        _presentation(),
        "ordered_preflip_records",
        None,
    )
    if not callable(current):
        raise RuntimeError(
            "Current Presentation + Audio generation "
            "does not yet expose GS462"
        )
    return current(
        records,
        baseline_order=baseline_order,
    )


def _install_state() -> None:
    current = getattr(
        _presentation(),
        "install_preflip_state",
        None,
    )
    if callable(current):
        current()


def _install_order() -> None:
    current = getattr(
        _presentation(),
        "install_preflip_order",
        None,
    )
    if callable(current):
        current()


def install() -> None:
    """Install GS462 slices when the warm authority generation supports them."""
    _install_state()
    _install_order()


def __getattr__(name: str):
    try:
        return getattr(_presentation(), name)
    except AttributeError:
        raise AttributeError(name) from None


__all__ = [
    "NEAR_ST_LINE_PCT",
    "RECENT_30S_FLIP_SECONDS",
    "PRE_FLIP_ATTENTION_BAND",
    "preflip_ignition_watch",
    "effective_attention_band",
    "ordered_preflip_records",
    "install",
]

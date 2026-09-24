"""GS459: warm-deploy-safe compatibility facade for price-trajectory attention.

Phase 32 splits GS459 by responsibility:
- Market Evidence owns provider-free 1-minute price-path metrics.
- Presentation + Audio owns trajectory attention and operator ordering.

GS459 remains the historical runtime seam used by GS462/GS463/GS465 and by the
existing regression suite. Both authorities are resolved lazily so a warm Streamlit
process retaining an older authority generation cannot fail module import/startup.
Available authority installers can bind independently; unavailable ones safely no-op
until a clean runtime loads the current authority generation.

This remains attention-only. No provider request, scanner threshold, qualification,
readiness, alert authority, execution, or order behavior is changed.
"""
from __future__ import annotations

from typing import Any


TRAJECTORY_BAND = 38
_MIN_3M_CHANGE_PCT = 1.0
_MIN_ACCELERATION_PCT_PER_MIN = 0.20
_MIN_POSITIVE_CLOSE_RATIO = 0.60
_MAX_GIVEBACK_FROM_5M_HIGH_PCT = 1.50
_MIN_FLOW_ACCELERATION = 1.20
_MIN_PARTICIPATION_SCORE = 40.0

_DISCOVERY_OWNER_ATTR = "_walter_gs459_price_trajectory_metrics_owner"
_ORDER_OWNER_ATTR = "_walter_gs459_price_trajectory_attention_owner"


def _market():
    from mide.authorities import market_evidence

    return market_evidence


def _presentation():
    from mide.authorities import presentation_audio

    return presentation_audio


def _number(value: Any, default: float = 0.0) -> float:
    current = getattr(_presentation(), "_trajectory_number", None)
    if callable(current):
        return current(value, default=default)
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _return_pct(start: float, end: float) -> float:
    current = getattr(_market(), "_price_trajectory_return_pct", None)
    if callable(current):
        return current(start, end)
    if start == 0:
        return 0.0
    return (end / start - 1.0) * 100.0


def price_trajectory_metrics(frame) -> dict:
    current = getattr(_market(), "price_trajectory_metrics", None)
    if not callable(current):
        raise RuntimeError(
            "Current Market Evidence generation does not yet expose GS459"
        )
    return current(frame)


def _supporting_flow(record: dict) -> bool:
    current = getattr(_presentation(), "_trajectory_supporting_flow", None)
    if not callable(current):
        raise RuntimeError(
            "Current Presentation + Audio generation does not yet expose GS459"
        )
    return current(record)


def trajectory_attention(record: dict) -> dict:
    current = getattr(_presentation(), "trajectory_attention", None)
    if not callable(current):
        raise RuntimeError(
            "Current Presentation + Audio generation does not yet expose GS459"
        )
    return current(record)


def effective_attention_band(record: dict) -> int:
    current = getattr(
        _presentation(),
        "effective_trajectory_attention_band",
        None,
    )
    if not callable(current):
        raise RuntimeError(
            "Current Presentation + Audio generation does not yet expose GS459"
        )
    return current(record)


def ordered_trajectory_records(
    records: list[dict],
    baseline_order=None,
) -> list[dict]:
    current = getattr(_presentation(), "ordered_trajectory_records", None)
    if not callable(current):
        raise RuntimeError(
            "Current Presentation + Audio generation does not yet expose GS459"
        )
    return current(records, baseline_order=baseline_order)


def _install_discovery_metrics() -> None:
    current = getattr(_market(), "install_price_trajectory_metrics", None)
    if callable(current):
        current()


def _install_operator_order() -> None:
    current = getattr(
        _presentation(),
        "install_price_trajectory_presentation",
        None,
    )
    if callable(current):
        current()


def install() -> None:
    """Install each GS459 authority slice when that warm generation is available."""
    _install_discovery_metrics()
    _install_operator_order()


def __getattr__(name: str):
    try:
        return getattr(_presentation(), name)
    except AttributeError:
        try:
            return getattr(_market(), name)
        except AttributeError:
            raise AttributeError(name) from None


__all__ = [
    "TRAJECTORY_BAND",
    "price_trajectory_metrics",
    "trajectory_attention",
    "effective_attention_band",
    "ordered_trajectory_records",
    "install",
]

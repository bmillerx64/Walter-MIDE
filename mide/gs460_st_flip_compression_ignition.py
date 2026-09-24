"""GS460: warm-deploy-safe compatibility facade for ST flip compression.

Phase 33 moves GS460 by responsibility:
- Market Evidence owns the 30s -> 1m -> 3m -> 5m flip-price compression facts.
- Presentation + Audio owns LOOK NOW / CHASE WAIT wording and tier-2 audio.

GS460 remains the historical runtime seam used by GS461/GS467/GS474 and regression
tests. Authorities are resolved lazily so a warm Streamlit process retaining an older
authority generation can keep its already-installed implementation rather than fail
startup. Missing new installers safely no-op until a clean runtime loads both current
authority modules.

The contract remains OPERATOR_ATTENTION_ONLY. No provider request, scanner threshold,
qualification, readiness, execution, or order behavior changes.
"""
from __future__ import annotations

from typing import Any


EARLY_LADDER = ("30s", "1m", "3m", "5m")
_LATER_CONTEXT = ("10m", "15m")
_RECENT_SECONDS = {
    "30s": 12 * 60.0,
    "1m": 18 * 60.0,
    "3m": 28 * 60.0,
    "5m": 40 * 60.0,
}
_NEW_SECONDS = {
    "30s": 90.0,
    "1m": 120.0,
    "3m": 240.0,
    "5m": 360.0,
}
_MAX_CLUSTER_SPAN_PCT = {2: 5.0, 3: 7.0, 4: 9.0}
LOOK_NOW_MAX_VWAP_DISTANCE_PCT = 5.0
_PROVENANCE = "ST_FLIP_PRICE_COMPRESSION"


def _market():
    from mide.authorities import market_evidence

    return market_evidence


def _presentation():
    from mide.authorities import presentation_audio

    return presentation_audio


def _number(value: Any) -> float | None:
    current = getattr(_market(), "st_flip_number", None)
    if callable(current):
        return current(value)
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _tf_detail(record: dict, label: str) -> dict:
    current = getattr(_market(), "st_flip_timeframe_detail", None)
    if not callable(current):
        raise RuntimeError(
            "Current Market Evidence generation does not yet expose GS460"
        )
    return current(record, label)


def _consecutive_recent_rungs(record: dict) -> list[dict]:
    current = getattr(
        _market(),
        "st_flip_consecutive_recent_rungs",
        None,
    )
    if not callable(current):
        raise RuntimeError(
            "Current Market Evidence generation does not yet expose GS460"
        )
    return current(record)


def _cluster_span_pct(prices: list[float]) -> float | None:
    current = getattr(_market(), "st_flip_cluster_span_pct", None)
    if not callable(current):
        raise RuntimeError(
            "Current Market Evidence generation does not yet expose GS460"
        )
    return current(prices)


def _supporting_flow(record: dict) -> bool:
    current = getattr(_market(), "st_flip_supporting_flow", None)
    if not callable(current):
        raise RuntimeError(
            "Current Market Evidence generation does not yet expose GS460"
        )
    return current(record)


def _next_frame_context(record: dict, depth: int) -> dict:
    current = getattr(_market(), "st_flip_next_frame_context", None)
    if not callable(current):
        raise RuntimeError(
            "Current Market Evidence generation does not yet expose GS460"
        )
    return current(record, depth)


def st_flip_compression(record: dict) -> dict:
    current = getattr(_market(), "st_flip_compression", None)
    if not callable(current):
        raise RuntimeError(
            "Current Market Evidence generation does not yet expose GS460"
        )
    return current(record)


def _state_with_compression(original, record: dict) -> dict:
    current = getattr(
        _presentation(),
        "state_with_st_flip_compression",
        None,
    )
    if not callable(current):
        raise RuntimeError(
            "Current Presentation + Audio generation does not yet expose GS460"
        )
    return current(original, record)


def _compression_change(record: dict) -> dict | None:
    current = getattr(
        _presentation(),
        "st_flip_compression_change",
        None,
    )
    if not callable(current):
        raise RuntimeError(
            "Current Presentation + Audio generation does not yet expose GS460"
        )
    return current(record)


def _spoken(label: str) -> str:
    current = getattr(_presentation(), "st_flip_spoken", None)
    if not callable(current):
        raise RuntimeError(
            "Current Presentation + Audio generation does not yet expose GS460"
        )
    return current(label)


def _compression_phrase(records: list[dict]) -> str:
    current = getattr(
        _presentation(),
        "st_flip_compression_phrase",
        None,
    )
    if not callable(current):
        raise RuntimeError(
            "Current Presentation + Audio generation does not yet expose GS460"
        )
    return current(records)


def _install_state() -> None:
    current = getattr(
        _presentation(),
        "install_st_flip_compression_state",
        None,
    )
    if callable(current):
        current()


def _install_alerts() -> None:
    current = getattr(
        _presentation(),
        "install_st_flip_compression_alerts",
        None,
    )
    if callable(current):
        current()


def install() -> None:
    """Install each GS460 presentation slice when that generation is available."""
    _install_state()
    _install_alerts()


def __getattr__(name: str):
    try:
        return getattr(_market(), name)
    except AttributeError:
        try:
            return getattr(_presentation(), name)
        except AttributeError:
            raise AttributeError(name) from None


__all__ = [
    "EARLY_LADDER",
    "LOOK_NOW_MAX_VWAP_DISTANCE_PCT",
    "st_flip_compression",
    "install",
]

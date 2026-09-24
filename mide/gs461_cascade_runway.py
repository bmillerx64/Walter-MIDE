"""GS461: warm-deploy-safe compatibility facade for cascade runway.

Phase 33 moves GS461 by responsibility:
- Market Evidence owns factual 10m/15m/30m/1h runway construction from already-owned
  history and the existing GS460 compression signal.
- Presentation + Audio owns explanation enrichment and annotation of GS460's existing
  tier-2 spoken alert.

GS461 remains the historical runtime seam. It still adds no provider work and reports
{"additional_history_requests": 0}. Authorities are resolved lazily so stale warm
Streamlit generations safely retain their already-installed legacy wrapper while clean
runtimes bind the consolidated owners.

No opportunity state, qualification, readiness, VWAP anti-chase, execution, or order
authority changes.
"""
from __future__ import annotations

from typing import Any

import pandas as pd

from .indicators import resample_ohlcv, supertrend


RUNWAY_ORDER = ("10m", "15m", "30m", "1h")
_RULES = {
    "10m": "10min",
    "15m": "15min",
    "30m": "30min",
    "1h": "60min",
}
AUTHORITY = "OPERATOR_ATTENTION_ONLY"
SOURCE = (
    "existing GS460/GS423 evidence + local resample of already-fetched "
    "current-session 1m bars"
)
_PROVENANCE = "ST_CASCADE_RUNWAY"
_INSTALL_GENERATION = object()


def _market():
    from mide.authorities import market_evidence

    return market_evidence


def _presentation():
    from mide.authorities import presentation_audio

    return presentation_audio


def _number(value: Any) -> float | None:
    current = getattr(_market(), "cascade_runway_number", None)
    if callable(current):
        return current(value)
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if pd.notna(number) else None


def _status_payload(
    label: str,
    *,
    available: bool,
    bullish: bool = False,
    close: float | None = None,
    supertrend_value: float | None = None,
    source: str,
) -> dict:
    current = getattr(
        _market(),
        "cascade_runway_status_payload",
        None,
    )
    if not callable(current):
        raise RuntimeError(
            "Current Market Evidence generation does not yet expose GS461"
        )
    return current(
        label,
        available=available,
        bullish=bullish,
        close=close,
        supertrend_value=supertrend_value,
        source=source,
    )


def _existing_status(record: dict, label: str) -> dict | None:
    current = getattr(
        _market(),
        "cascade_runway_existing_status",
        None,
    )
    if not callable(current):
        raise RuntimeError(
            "Current Market Evidence generation does not yet expose GS461"
        )
    return current(record, label)


def _local_status(day: pd.DataFrame, label: str) -> dict:
    current = getattr(
        _market(),
        "cascade_runway_local_status",
        None,
    )
    if not callable(current):
        raise RuntimeError(
            "Current Market Evidence generation does not yet expose GS461"
        )
    return current(
        day,
        label,
        resample_fn=resample_ohlcv,
        supertrend_fn=supertrend,
    )


def summarize_runway(
    compression: dict,
    statuses: dict[str, dict],
) -> dict:
    current = getattr(
        _market(),
        "summarize_cascade_runway",
        None,
    )
    if not callable(current):
        raise RuntimeError(
            "Current Market Evidence generation does not yet expose GS461"
        )
    return current(compression, statuses)


def build_cascade_runway(record: dict, raw_rows, client) -> dict:
    current = getattr(_market(), "build_cascade_runway", None)
    if not callable(current):
        raise RuntimeError(
            "Current Market Evidence generation does not yet expose GS461"
        )
    return current(record, raw_rows, client)


def _runway_text(runway: dict) -> str:
    current = getattr(_presentation(), "cascade_runway_text", None)
    if not callable(current):
        raise RuntimeError(
            "Current Presentation + Audio generation does not yet expose GS461"
        )
    return current(runway)


def _state_with_runway(original, record: dict) -> dict:
    current = getattr(
        _presentation(),
        "state_with_cascade_runway",
        None,
    )
    if not callable(current):
        raise RuntimeError(
            "Current Presentation + Audio generation does not yet expose GS461"
        )
    return current(original, record)


def _install_evidence() -> None:
    current = getattr(
        _market(),
        "install_cascade_runway_evidence",
        None,
    )
    if callable(current):
        current()


def _install_state() -> None:
    current = getattr(
        _presentation(),
        "install_cascade_runway_state",
        None,
    )
    if callable(current):
        current()


def _alert_runway(records: list[dict]) -> str:
    current = getattr(
        _presentation(),
        "cascade_runway_alert",
        None,
    )
    if not callable(current):
        raise RuntimeError(
            "Current Presentation + Audio generation does not yet expose GS461"
        )
    return current(records)


def _install_alerts() -> None:
    current = getattr(
        _presentation(),
        "install_cascade_runway_alerts",
        None,
    )
    if callable(current):
        current()


def install() -> None:
    """Install each GS461 authority slice when that generation is available."""
    _install_evidence()
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
    "RUNWAY_ORDER",
    "AUTHORITY",
    "SOURCE",
    "summarize_runway",
    "build_cascade_runway",
    "install",
]

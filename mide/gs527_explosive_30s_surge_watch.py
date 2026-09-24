"""GS527: warm-deploy-safe Presentation + Audio facade for explosive 30s attention.

GS527's presentation-only EARLY SURGE WATCH now lives in authoritative Presentation +
Audio. The historical module remains the validated calibration/monkeypatch seam used
by the regression suite and late-runtime wrapper graph.

The original thresholds and owner/provenance names remain local. Presentation + Audio
reads those facade values at evaluation time and calls back through the historical
helper/state/order/audio names where the original module used module globals. This
preserves retained-runtime and monkeypatch behavior while removing duplicate authority.

A stale warm Presentation generation fails closed: no surge is invented, visible
state/order are left unchanged, audio stays silent, and install() safely no-ops.
Qualification, readiness, anti-chase, retest, Mission Rank, execution, and orders are
unchanged.
"""

from __future__ import annotations

from typing import Any


FRESH_BURST_SECONDS = 90.0
MIN_VOLUME_ACCELERATION_30S = 3.0
MIN_DOLLAR_FLOW_ACCELERATION_30S = 3.0
_PROVENANCE = "GS527_EXPLOSIVE_30S_SURGE"
_STATE_OWNER = "_walter_gs527_explosive_30s_surge_state_owner"
_ORDER_OWNER = "_walter_gs527_explosive_30s_surge_order_owner"
_AUDIO_OWNER = "_walter_gs527_explosive_30s_surge_audio_owner"


def _presentation():
    from mide.authorities import presentation_audio

    return presentation_audio


def _number(value: Any) -> float | None:
    current = getattr(_presentation(), "explosive_30s_number", None)
    if callable(current):
        return current(value)
    try:
        return float(value) if value is not None and value != "" else None
    except (TypeError, ValueError):
        return None


def explosive_30s_surge(record: dict) -> dict:
    current = getattr(_presentation(), "explosive_30s_surge", None)
    if callable(current):
        return current(record)
    return {
        "active": False,
        "symbol": str(record.get("symbol") or "").strip().upper(),
        "flip_age_seconds": None,
        "volume_acceleration_30s": None,
        "dollar_flow_acceleration_30s": None,
        "thirty_second_above_vwap": False,
        "thirty_second_bullish": False,
        "authority": "OPERATOR_ATTENTION_ONLY",
        "entry_authority_changed": False,
        "qualification_authority_changed": False,
        "readiness_authority_changed": False,
    }


def state_with_explosive_30s(original, record: dict) -> dict:
    current = getattr(_presentation(), "state_with_explosive_30s", None)
    if not callable(current):
        return original(record)
    return current(original, record)


def _attention_band(record: dict) -> int:
    current = getattr(_presentation(), "explosive_30s_attention_band", None)
    if not callable(current):
        return 1
    return int(current(record))


def ordered_explosive_30s_records(
    records: list[dict],
    baseline_order=None,
) -> list[dict]:
    current = getattr(_presentation(), "ordered_explosive_30s_records", None)
    if not callable(current):
        rows = list(records or [])
        return list(
            baseline_order(rows)
            if baseline_order is not None
            else rows
        )
    return current(
        records,
        baseline_order=baseline_order,
    )


def explosive_30s_audio_phrase(records: list[dict]) -> str:
    current = getattr(_presentation(), "explosive_30s_audio_phrase", None)
    if not callable(current):
        return ""
    return current(records)


def _install_state() -> None:
    current = getattr(_presentation(), "install_explosive_30s_state", None)
    if callable(current):
        current()


def _install_order() -> None:
    current = getattr(_presentation(), "install_explosive_30s_order", None)
    if callable(current):
        current()


def _install_audio() -> None:
    current = getattr(_presentation(), "install_explosive_30s_audio", None)
    if callable(current):
        current()


def install() -> None:
    """Install GS527 slices when the warm authority generation supports them."""
    _install_state()
    _install_order()
    _install_audio()


def __getattr__(name: str):
    try:
        return getattr(_presentation(), name)
    except AttributeError:
        raise AttributeError(name) from None


__all__ = [
    "FRESH_BURST_SECONDS",
    "MIN_VOLUME_ACCELERATION_30S",
    "MIN_DOLLAR_FLOW_ACCELERATION_30S",
    "explosive_30s_surge",
    "state_with_explosive_30s",
    "ordered_explosive_30s_records",
    "explosive_30s_audio_phrase",
    "install",
]

"""Compatibility facade for Walter Next state-first operator ordering.

The historical GS463 ordering rule now lives in the authoritative
mide.authorities.presentation_audio sorter. This module preserves the validated
import/install surface.
"""

from __future__ import annotations

from .authorities import presentation_audio as _presentation


WATCH_FOR_ENTRY_BAND = _presentation.STATE_FIRST_WATCH_FOR_ENTRY_BAND
LOOK_NOW_BAND = _presentation.STATE_FIRST_LOOK_NOW_BAND
JET_FUEL_BAND = _presentation.STATE_FIRST_JET_FUEL_BAND
EARLY_WATCH_BAND = _presentation.STATE_FIRST_EARLY_WATCH_BAND
FRESH_MATURATION_BAND = _presentation.STATE_FIRST_FRESH_MATURATION_BAND
TRAJECTORY_BAND = _presentation.STATE_FIRST_TRAJECTORY_BAND
RECENT_CONFIRMATION_BAND = _presentation.STATE_FIRST_RECENT_CONFIRMATION_BAND
DEVELOPING_BAND = _presentation.STATE_FIRST_DEVELOPING_BAND
CHASE_WAIT_BAND = _presentation.STATE_FIRST_CHASE_WAIT_BAND
OTHER_BAND = _presentation.STATE_FIRST_OTHER_BAND


def effective_operator_attention_band(record: dict) -> int:
    return _presentation.effective_operator_attention_band(record)


def ordered_state_first_records(records: list[dict], baseline_order=None) -> list[dict]:
    return _presentation.ordered_state_first_records(records, baseline_order=baseline_order)


def install() -> None:
    _presentation.activate_operator_order_stage("state_first")


__all__ = [
    "effective_operator_attention_band",
    "ordered_state_first_records",
    "install",
]

"""Compatibility coordinator for GS393/GS439 ignition truth and action-first decay.

The historical module mixed four responsibilities. Walter Next now assigns them to
their authoritative components while preserving this import/install surface and its
original installation order:

1. Market Evidence owns primary 1m ignition truth.
2. Thesis / State owns what fresh ignition means to Opportunity State.
3. Presentation + Audio owns action-first extreme-banner TTL/decay.
4. Replay / Validation owns validation-sequence enrichment.
"""

from __future__ import annotations

from .authorities import market_evidence as _market
from .authorities import presentation_audio as _presentation


IGNITION_MAX_VWAP_DISTANCE_PCT = _market.IGNITION_MAX_VWAP_DISTANCE_PCT
IGNITION_FLIP_RECENT_SECONDS = _market.IGNITION_FLIP_RECENT_SECONDS
IGNITION_RECLAIM_RECENT_BARS = _market.IGNITION_RECLAIM_RECENT_BARS
EXTREME_DO_NOT_CHASE_TOP_TTL_SECONDS = (
    _presentation.EXTREME_DO_NOT_CHASE_TOP_TTL_SECONDS
)


def ignition_evidence(record: dict) -> dict:
    return _market.ignition_evidence(record)


def _state_with_ignition(original, record: dict) -> dict:
    from .authorities import thesis_state

    return thesis_state.state_with_ignition(original, record)


def _install_ignition_state() -> None:
    from .authorities import thesis_state

    thesis_state.install_ignition_state()


def _install_extreme_banner_decay() -> None:
    _presentation.install_extreme_banner_decay()


def _install_recorder_truth() -> None:
    from .authorities import replay_validation

    replay_validation.install_ignition_validation_sequence()


def reset_state() -> None:
    _presentation.reset_extreme_banner_decay_state()


def install() -> None:
    """Preserve GS393's historical cross-authority installation order."""
    _install_ignition_state()
    _install_extreme_banner_decay()
    _install_recorder_truth()


__all__ = [
    "IGNITION_MAX_VWAP_DISTANCE_PCT",
    "IGNITION_FLIP_RECENT_SECONDS",
    "IGNITION_RECLAIM_RECENT_BARS",
    "EXTREME_DO_NOT_CHASE_TOP_TTL_SECONDS",
    "ignition_evidence",
    "reset_state",
    "install",
]

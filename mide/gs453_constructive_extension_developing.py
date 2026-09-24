"""GS453: compatibility facade for constructive-extension presentation semantics.

Phase 27 moves the GS453 implementation into authoritative Presentation + Audio.
This facade intentionally resolves the new authority lazily so a warm Streamlit
deployment holding an older Presentation + Audio generation cannot fail at import
time. If that older generation is still retained during deployment, install() leaves
the already-active GS453 wrapper alone; a clean process/restart binds the consolidated
authority normally.

Behavior is unchanged: only CHASE / WAIT display semantics may soften to DEVELOPING
for a bounded constructive extension. Trading qualification, readiness, anti-chase
locks, alerts, execution, and orders remain authoritative elsewhere.
"""
from __future__ import annotations


# Historical compatibility constants. The authoritative values live in
# mide.authorities.presentation_audio on clean/current runtimes.
MIN_VWAP_DISTANCE_PCT = 2.0
MAX_VWAP_DISTANCE_PCT = 5.0
MIN_ALIGNMENT_SCORE = 2
MAX_10M_PRICE_CHANGE_PCT = 6.0
PARTICIPATION_REARM_LEVEL = 40.0
MIN_VOLUME_ACCELERATION = 1.0
MIN_DOLLAR_FLOW_ACCELERATION = 1.25


def _presentation():
    from mide.authorities import presentation_audio

    return presentation_audio


def constructive_extension_evidence(record: dict) -> dict:
    """Delegate GS453 evidence to Presentation + Audio on current runtimes."""
    current = getattr(_presentation(), "constructive_extension_evidence", None)
    if not callable(current):
        raise RuntimeError(
            "Current Presentation + Audio generation does not yet expose GS453"
        )
    return current(record)


def _state_with_constructive_extension(original, record: dict) -> dict:
    """Historical private seam retained for GS453 regressions and callers."""
    current = getattr(_presentation(), "state_with_constructive_extension", None)
    if not callable(current):
        raise RuntimeError(
            "Current Presentation + Audio generation does not yet expose GS453"
        )
    return current(original, record)


def install() -> None:
    """Install lazily and tolerate an older retained authority generation."""
    current = getattr(
        _presentation(),
        "install_constructive_extension_presentation",
        None,
    )
    if not callable(current):
        # Warm deploy safety: the pre-Phase-27 GS453 wrapper may already be active.
        # Do not crash app startup while an older authority module remains retained.
        return
    current()


def __getattr__(name: str):
    try:
        return getattr(_presentation(), name)
    except AttributeError:
        raise AttributeError(name) from None


__all__ = [
    "MIN_VWAP_DISTANCE_PCT",
    "MAX_VWAP_DISTANCE_PCT",
    "MIN_ALIGNMENT_SCORE",
    "MAX_10M_PRICE_CHANGE_PCT",
    "PARTICIPATION_REARM_LEVEL",
    "MIN_VOLUME_ACCELERATION",
    "MIN_DOLLAR_FLOW_ACCELERATION",
    "constructive_extension_evidence",
    "install",
]

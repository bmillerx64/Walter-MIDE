"""GS532: warm-deploy-safe Replay / Validation facade for 3m-retest entry shadow.

The held-3m-retest recovery counterfactual is observational calibration only and now
lives in authoritative Replay / Validation. This historical module retains the
validated VWAP/participation/expansion thresholds so replay experiments and regression
tests keep their existing tuning seam.

A stale warm Replay / Validation generation fails closed: shadow_entry_ready is False
and no live qualification, readiness, ranking, alert, execution, or order authority is
changed.
"""

from __future__ import annotations


VWAP_MIN_PCT = -0.75
VWAP_MAX_PCT = 2.0
MIN_PARTICIPATION = 60.0
MIN_EXPANSION = 55.0


def _replay():
    from mide.authorities import replay_validation

    return replay_validation


def retest_entry_shadow(record: dict) -> dict:
    current = getattr(
        _replay(),
        "retest_entry_shadow",
        None,
    )
    if callable(current):
        return current(record)

    return {
        "authority": "OBSERVATIONAL_ONLY",
        "shadow_entry_ready": False,
        "checks": {},
        "failed_conditions": [
            "Replay / Validation unavailable"
        ],
        "three_minute_retest_event": {},
        "discipline_sequence": {},
        "vwap_distance_pct": None,
        "participation_score": None,
        "expansion_quality": None,
        "thresholds": {
            "vwap_min_pct": VWAP_MIN_PCT,
            "vwap_max_pct": VWAP_MAX_PCT,
            "participation_min": MIN_PARTICIPATION,
            "expansion_min": MIN_EXPANSION,
        },
        "trading_authority_changed": False,
    }


def __getattr__(name: str):
    try:
        return getattr(_replay(), name)
    except AttributeError:
        raise AttributeError(name) from None


__all__ = [
    "VWAP_MIN_PCT",
    "VWAP_MAX_PCT",
    "MIN_PARTICIPATION",
    "MIN_EXPANSION",
    "retest_entry_shadow",
]

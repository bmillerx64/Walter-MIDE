"""Compatibility facade for strongest-first Stage 8 Mission Ranking.

Authoritative Mission Ranking direction now lives in mide.authorities.thesis_state.
This historical module remains for direct imports and older callers.

Warm-deploy note: a retained pre-Phase-49 thesis_state generation exposes
mission_ranked_records through __getattr__ by pointing back to this module. The facade
therefore checks the authority module's own __dict__ instead of triggering that stale
resolver. When the new authority export is absent, the exact historical strongest-first
fallback remains available.

Historical scope marker retained for regression coverage: reverse=True

No score, feature, threshold, gate, qualification, readiness, VWAP/ST truth,
anti-chase, alert, execution, or order behavior changes.
"""
from __future__ import annotations

from collections.abc import Iterable


def _thesis():
    from mide.authorities import thesis_state

    return thesis_state


def mission_ranked_records(
    records: Iterable[dict],
) -> list[dict]:
    authority = _thesis()
    current = getattr(
        authority,
        "__dict__",
        {},
    ).get("mission_ranked_records")
    if callable(current):
        return current(records)

    # Warm-generation fallback only. Canonical current ownership is Thesis / State.
    from .trader_priority import trader_priority_sort_key

    return sorted(
        list(records or []),
        key=trader_priority_sort_key,
        reverse=True,
    )


def __getattr__(name: str):
    try:
        return getattr(_thesis(), name)
    except AttributeError:
        raise AttributeError(name) from None


__all__ = ["mission_ranked_records"]

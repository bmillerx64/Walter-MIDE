"""GS498: make Mission Ranking direction match Walter's priority contract.

Sept. 18 live backup evidence exposed an upstream ranking defect after GS497 made
Mission Ranking visible in operator ordering. trader_priority_sort_key is a
higher-is-better key throughout Walter; its tests and other presentation sorters use
descending order. The live Stage 8 callback in app.py instead sorted the same key
ascending, assigning mission_rank=1 to the weakest expansion-qualified record.

GS498 centralizes the live Stage 8 ordering in one explicit helper and sorts the
existing key descending. It changes no score, feature, threshold, gate, qualification,
readiness, VWAP/ST truth, anti-chase rule, alert, execution, or order behavior. It
only corrects which already-qualified candidate receives rank 1, 2, 3, ...
"""
from __future__ import annotations

from collections.abc import Iterable

from .trader_priority import trader_priority_sort_key


def mission_ranked_records(records: Iterable[dict]) -> list[dict]:
    """Return Expansion-qualified records strongest-first for Stage 8 ranking."""
    return sorted(
        list(records or []),
        key=trader_priority_sort_key,
        reverse=True,
    )

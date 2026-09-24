"""GS423: warm-deploy-safe facade for efficient convergence market evidence.

Phase 29 moves GS423's multitimeframe maturation handoff into Walter Next's
authoritative Market Evidence component. GS423 remains at its historical startup
location and is still called by GS455 before the later explicit startup install.

The facade resolves Market Evidence lazily. If a warm Streamlit deployment retains
an older Market Evidence generation that does not yet expose GS423, install() safely
leaves the already-active legacy GS423 wrapper in place instead of failing startup.
A clean runtime binds the consolidated implementation normally.

The contract remains observational only: existing 1m/3m/5m/10m SuperTrend work is
reused, only the local 15m maturation layer is additional, and no provider history
request, scoring, ranking, qualification, readiness, alert/audio, execution, or order
authority is changed.
"""
from __future__ import annotations

from typing import Any

import pandas as pd


AUTHORITY = "OBSERVATIONAL_ONLY"
SOURCE = (
    "GS378 already-computed 1m/3m/5m/10m state plus one local 15m maturation pass; "
    "no additional provider history request"
)


def _market():
    from mide.authorities import market_evidence

    return market_evidence


def _number(value: Any) -> float | None:
    current = getattr(_market(), "_convergence_number", None)
    if callable(current):
        return current(value)
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if pd.notna(number) else None


def confirmation_details_with_maturation(
    day: pd.DataFrame,
    primary_series: pd.Series,
) -> tuple[int, dict]:
    current = getattr(_market(), "confirmation_details_with_maturation", None)
    if not callable(current):
        raise RuntimeError(
            "Current Market Evidence generation does not yet expose GS423"
        )
    return current(day, primary_series)


def _fallback_event(record: dict, label: str) -> dict:
    current = getattr(_market(), "_convergence_fallback_event", None)
    if not callable(current):
        raise RuntimeError(
            "Current Market Evidence generation does not yet expose GS423"
        )
    return current(record, label)


def build_efficient_maturation_evidence(record: dict, raw_rows, client) -> dict:
    current = getattr(_market(), "build_efficient_maturation_evidence", None)
    if not callable(current):
        raise RuntimeError(
            "Current Market Evidence generation does not yet expose GS423"
        )
    return current(record, raw_rows, client)


def install() -> None:
    current = getattr(_market(), "install_convergence_handoff_evidence", None)
    if not callable(current):
        # Warm-deploy safety: pre-Phase-29 GS423 may already own the active chain.
        return
    current()


def __getattr__(name: str):
    try:
        return getattr(_market(), name)
    except AttributeError:
        raise AttributeError(name) from None


__all__ = [
    "AUTHORITY",
    "SOURCE",
    "confirmation_details_with_maturation",
    "build_efficient_maturation_evidence",
    "install",
]

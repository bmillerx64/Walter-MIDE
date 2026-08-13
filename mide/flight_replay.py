"""Replay helpers that bridge Walter's Flight Recorder and decision evidence.

This module is read-only.  It never fetches market data and never changes live
scoring, ranking, alerts, or candidate state.
"""

from __future__ import annotations

from mide.decision_replay import replay_decision


class ReplayNotAvailable(LookupError):
    """Raised when a requested historical decision cannot be replayed."""


def replay_recorded_symbol(scan: dict, symbol: str) -> dict:
    """Replay one symbol directly from the immutable evidence stored in a scan."""
    symbol = str(symbol or "").strip().upper()
    path = next(
        (
            item for item in scan.get("symbols", [])
            if str(item.get("symbol") or "").upper() == symbol
        ),
        None,
    )
    if not path:
        raise ReplayNotAvailable(f"{symbol} is not present in scan {scan.get('scan_id')}")

    evidence = path.get("decision_time_evidence")
    if not evidence:
        raise ReplayNotAvailable(
            f"scan {scan.get('scan_id')} predates immutable decision-time replay evidence"
        )
    return replay_decision(evidence)


def replay_scan(scan: dict) -> list[dict]:
    """Replay every symbol in a scan that contains immutable decision evidence."""
    results = []
    for path in scan.get("symbols", []):
        if path.get("decision_time_evidence"):
            results.append(replay_decision(path["decision_time_evidence"]))
    return results

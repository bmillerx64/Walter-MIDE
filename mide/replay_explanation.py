"""Human-readable explanations built only from immutable replay results.

This module is read-only. It never fetches market data and never participates in
live discovery, scoring, ranking, qualification, alerts, or candidate state.
"""

from __future__ import annotations

from copy import deepcopy


def explain_replay(replay: dict) -> dict:
    """Return a concise explanation whose claims are bounded by frozen replay data."""
    replay = deepcopy(replay or {})
    if not replay.get("integrity_verified"):
        raise ValueError("replay explanation requires integrity-verified evidence")

    symbol = str(replay.get("symbol") or "").upper()
    state = str(replay.get("replay_state") or "OBSERVE")
    blockers = list(replay.get("blockers") or [])
    inputs = deepcopy(replay.get("decision_inputs") or {})

    state_text = {
        "PARTICIPATION_BLOCKED": "was blocked at the participation gate",
        "STRUCTURE_BLOCKED": "was blocked at the structure gate",
        "ENTRY_READY": "was entry-ready",
        "WATCH": "qualified for watch but was not entry-ready",
        "OBSERVE": "remained observe-only",
    }.get(state, f"was recorded as {state}")

    if blockers:
        blocker_text = "; ".join(str(item) for item in blockers[:3])
        explanation = f"{symbol} {state_text}. Recorded blocker evidence: {blocker_text}."
    else:
        explanation = f"{symbol} {state_text}. No recorded blocker was present in the immutable evidence."

    return {
        "scan_id": replay.get("scan_id"),
        "scan_timestamp": replay.get("scan_timestamp"),
        "symbol": symbol,
        "integrity_verified": True,
        "evidence_sha256": replay.get("evidence_sha256"),
        "replay_state": state,
        "recorded_status": replay.get("recorded_status"),
        "explanation": explanation,
        "blockers": blockers,
        "decision_inputs": inputs,
        "evidence_source": "immutable decision_time_evidence",
    }

"""Human-readable summaries of Walter deterministic replay results."""

from __future__ import annotations


def summarize_replay(replay: dict) -> str:
    """Produce a compact explanation without recalculating the historical decision."""
    symbol = replay.get("symbol") or "UNKNOWN"
    state = replay.get("replay_state") or "UNKNOWN"
    blockers = replay.get("blockers") or []
    text = f"{symbol}: {state}"
    if blockers:
        text += " — " + "; ".join(str(item) for item in blockers)
    return text

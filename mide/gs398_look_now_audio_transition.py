"""GS398: guarantee one distinct LOOK NOW alert for a genuine visible transition.

Live validation on 2026-09-08 left one operator-facing gap after GS397: a symbol can
visibly enter LOOK NOW while another lower-priority alert path (for example a new
coiling/early-setup message or a different ordinary state change) wins the single
per-scan alert slot.  The browser broker then behaves correctly, but the operator
never hears the distinctive LOOK NOW cadence for the transition that is actually
visible on screen.

GS398 is presentation/audio routing only.  It never changes opportunity state,
qualification, readiness, ranking, market data, thresholds, execution, or orders.
The contract is:

* derive LOOK NOW only from GS311's existing transition truth;
* operate only on records already admitted to the trader-visible workflow;
* preserve any simultaneous tier-3 WATCH FOR ENTRY / ENTRY READY / ENTRY WINDOW alert;
* otherwise let a genuine new LOOK NOW transition outrank routine/coiling audio;
* rely on GS366 completed-scan dedupe and GS367 browser aggregation for exactly-once
  delivery on Streamlit reruns.
"""
from __future__ import annotations

from .gs365_chime_semantic_classifier import semantic_chime_count

LOOK_NOW = "LOOK NOW"
LOOK_NOW_TIER = 2
HIGH_PRIORITY_TIER = 3


def visible_look_now_transitions(records: list[dict]) -> list[dict]:
    """Return genuine unified transitions whose new visible state is LOOK NOW.

    Callers pass the already filtered operator-visible record set.  GS311 owns the
    transition semantics, including explicit first-actionable observations and
    prior-state comparison, so GS398 does not invent a second transition model.
    """
    from . import gs311_unified_voice as voice

    return [
        dict(change)
        for change in voice.unified_state_changes(list(records or []))
        if str(change.get("to") or "").strip().upper() == LOOK_NOW
    ]


def look_now_alert_phrase(records: list[dict]) -> str:
    """Build the explicit tier-2 phrase for the newest visible LOOK NOW event."""
    changes = visible_look_now_transitions(records)
    if not changes:
        return ""

    first = changes[0]
    symbol = str(first.get("symbol") or "Symbol").strip().upper() or "SYMBOL"
    phrase = f"{symbol}. LOOK NOW."
    if len(changes) > 1:
        extra = len(changes) - 1
        phrase += (
            f" {extra} additional LOOK NOW opportunity"
            f"{'ies' if extra != 1 else ''}."
        )
    return phrase


def prioritize_visible_look_now_alert(
    records: list[dict], existing_phrase: str
) -> str:
    """Promote LOOK NOW above routine audio while preserving tier-3 urgency."""
    current = str(existing_phrase or "")
    look_now = look_now_alert_phrase(records)
    if not look_now:
        return current

    if current and semantic_chime_count(current) >= HIGH_PRIORITY_TIER:
        return current
    return look_now


def blocks_lower_priority_coiling(phrase: str) -> bool:
    """Whether the selected alert is important enough to suppress routine coiling."""
    text = str(phrase or "")
    return bool(text) and semantic_chime_count(text) >= LOOK_NOW_TIER

"""GS398: guarantee one distinct LOOK NOW alert for a genuine visible transition.

Live validation on 2026-09-08 left one operator-facing gap after GS397: a symbol can
visibly enter LOOK NOW while another lower-priority alert path (for example a new
coiling/early-setup message or a different ordinary state change) wins the single
per-scan alert slot. The browser broker then behaves correctly, but the operator
never hears the distinctive LOOK NOW cadence for the transition actually visible.

GS398 is presentation/audio routing only. It never changes opportunity state,
qualification, readiness, ranking, market data, thresholds, execution, or orders.
The contract is:

* derive LOOK NOW only from GS311's existing transition truth;
* operate only on records already admitted to the trader-visible workflow;
* preserve any simultaneous tier-3 WATCH FOR ENTRY / ENTRY READY / ENTRY WINDOW alert;
* otherwise let a genuine new LOOK NOW transition outrank routine/coiling audio;
* include LOOK NOW in the state-change signature used by app-level rerun dedupe;
* rely on GS366 completed-scan dedupe and GS367 browser aggregation for exactly-once
  delivery on Streamlit reruns.
"""
from __future__ import annotations

from functools import wraps

from .gs365_chime_semantic_classifier import semantic_chime_count

LOOK_NOW = "LOOK NOW"
LOOK_NOW_TIER = 2
HIGH_PRIORITY_TIER = 3


def visible_look_now_transitions(records: list[dict]) -> list[dict]:
    """Return genuine unified transitions whose new visible state is LOOK NOW.

    Callers pass the already filtered operator-visible record set. GS311 owns the
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
        noun = "opportunity" if extra == 1 else "opportunities"
        phrase += f" {extra} additional LOOK NOW {noun}."
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


def _merge_look_now_changes(records: list[dict], existing: list[dict]) -> list[dict]:
    """Put genuine LOOK NOW transitions into the app's transition signature."""
    look_now = visible_look_now_transitions(records)
    if not look_now:
        return list(existing or [])

    merged = list(look_now)
    seen = {
        (
            str(change.get("symbol") or "").upper(),
            str(change.get("from") or ""),
            str(change.get("to") or ""),
        )
        for change in merged
    }
    for change in existing or []:
        key = (
            str(change.get("symbol") or "").upper(),
            str(change.get("from") or ""),
            str(change.get("to") or ""),
        )
        if key not in seen:
            merged.append(change)
            seen.add(key)
    return merged


def install() -> None:
    """Install LOOK NOW routing after GS397 and before app.py binds helpers."""
    from . import early_setup, escalation, ui

    current_changes = escalation.escalation_state_changes
    if not getattr(current_changes, "_gs398_look_now_signature", False):
        @wraps(current_changes)
        def state_changes(records: list[dict]) -> list[dict]:
            rows = list(records or [])
            return _merge_look_now_changes(rows, current_changes(rows))

        state_changes._gs398_look_now_signature = True
        state_changes._gs398_original = current_changes
        escalation.escalation_state_changes = state_changes

    current_phrase = escalation.escalation_alert_phrase
    if not getattr(current_phrase, "_gs398_look_now_priority", False):
        @wraps(current_phrase)
        def alert_phrase(records: list[dict]) -> str:
            rows = list(records or [])
            return prioritize_visible_look_now_alert(rows, current_phrase(rows))

        alert_phrase._gs398_look_now_priority = True
        alert_phrase._gs398_original = current_phrase
        escalation.escalation_alert_phrase = alert_phrase

    current_early = early_setup.newly_entered_symbols
    if not getattr(current_early, "_gs398_look_now_priority", False):
        @wraps(current_early)
        def newly_entered_symbols(records: list[dict], active_symbols: set[str]):
            rows = list(records or [])
            entered, active = current_early(rows, active_symbols)
            if not entered:
                return entered, active
            visible = ui.actionable_candidate_records(rows)
            if look_now_alert_phrase(visible):
                # Preserve active-set bookkeeping but suppress only this lower-tier
                # coiling delivery so app.py falls through to the LOOK NOW alert.
                return [], active
            return entered, active

        newly_entered_symbols._gs398_look_now_priority = True
        newly_entered_symbols._gs398_original = current_early
        early_setup.newly_entered_symbols = newly_entered_symbols

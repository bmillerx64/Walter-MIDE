"""GS419: guarantee one audible heartbeat for every completed scan.

Live validation on 2026-09-10 showed GS418 correctly restored tier-1 audibility, but
Walter could still complete a scan in silence whenever the existing alert phrase was
empty (for example, only DEVELOPING/CHASE-WAIT records and no Strengthening, LOOK NOW,
or entry-urgency event).

GS419 restores the operator contract without changing alert truth: every completed
scan gets at least the routine tier-1 browser tone when audible alerts are enabled;
existing tier-2 LOOK NOW and tier-3 entry-urgency alerts retain priority through the
GS367 per-scan highest-tier broker. The heartbeat itself is tone-only and adds no
speech.

Audio/presentation only. No discovery, market data, VWAP/ST, participation, expansion,
scoring, qualification, readiness, thresholds, cadence, execution, or orders change.
"""
from __future__ import annotations

from functools import wraps


HEARTBEAT_PHRASE = "__WALTER_COMPLETED_SCAN_HEARTBEAT__"


def _has_existing_scan_alert_fallback(records: list[dict]) -> bool:
    """Leave app.py's existing Strengthening/Entry Ready fallback untouched."""
    for record in records or []:
        status = str(record.get("candidate_status") or "").strip().upper()
        if status in {"STRENGTHENING", "ENTRY READY"}:
            return True
    return False


def heartbeat_phrase(records: list[dict], existing_phrase: str) -> str:
    """Return a tone-only sentinel only when the scan otherwise has no alert phrase."""
    phrase = str(existing_phrase or "")
    if phrase or _has_existing_scan_alert_fallback(records):
        return phrase
    return HEARTBEAT_PHRASE


def heartbeat_markup(state) -> str:
    """Build the tier-1 broker registration for the currently completed scan."""
    from . import gs367_browser_audio_broker as broker
    from .gs366_rerun_alert_dedupe import completed_scan_token

    token = completed_scan_token(state)
    if token == "no-completed-scan":
        return ""
    return broker.browser_broker_markup(token, 1)


def _inherit(wrapper, wrapped) -> None:
    for name, value in getattr(wrapped, "__dict__", {}).items():
        if name.startswith("_gs") and not hasattr(wrapper, name):
            setattr(wrapper, name, value)


def install() -> None:
    """Install after GS414 so app.py binds the final heartbeat-aware alert callables."""
    from . import escalation, ui

    current_phrase = escalation.escalation_alert_phrase
    if not getattr(current_phrase, "_gs419_completed_scan_heartbeat", False):
        @wraps(current_phrase)
        def escalation_alert_phrase(records: list[dict]) -> str:
            rows = list(records or [])
            return heartbeat_phrase(rows, current_phrase(rows))

        escalation_alert_phrase._gs419_completed_scan_heartbeat = True
        escalation_alert_phrase._gs419_original = current_phrase
        escalation.escalation_alert_phrase = escalation_alert_phrase

    current_play = ui.play_alert
    if getattr(current_play, "_gs419_completed_scan_heartbeat", False):
        return

    @wraps(current_play)
    def play_alert(sound_path: str, phrase: str, voice_name: str = ""):
        if str(phrase or "") != HEARTBEAT_PHRASE:
            return current_play(sound_path, phrase, voice_name)

        markup = heartbeat_markup(ui.st.session_state)
        if not markup:
            return None
        ui.st.components.v1.html(markup, height=0, scrolling=False)
        return None

    _inherit(play_alert, current_play)
    play_alert._gs419_completed_scan_heartbeat = True
    play_alert._gs419_original = current_play
    ui.play_alert = play_alert

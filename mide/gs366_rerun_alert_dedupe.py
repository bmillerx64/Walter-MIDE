"""GS366: deliver each completed-scan alert only once across Streamlit reruns.

Presentation/audio only. Scanner membership, market data, scoring, ranking,
qualification, readiness, thresholds, execution, and orders are unchanged.

Live 2026-09-02 evidence showed that an ordinary one-chime alert could be emitted
again when Streamlit reran the same completed scan. The application only persisted
a dedupe key for escalation-state transitions; fallback scan alerts with no state
transition therefore remained replayable on every rerun. Several one-chime
components arriving close together sound like one false triple alert.

This wrapper scopes delivery to the immutable CompletedScan timestamp and remembers
every phrase already emitted for that scan. A new completed scan resets the delivery
registry, so a genuinely new event may alert even when its wording matches a prior
scan. GS367 is installed immediately afterward to aggregate distinct alert paths
for the same scan into one browser-scoped audible cadence.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, MutableMapping


_SCAN_TOKEN_KEY = "_walter_audio_delivery_scan_token"
_DELIVERED_KEY = "_walter_audio_delivered_signatures"
_SUPPRESSED_COUNT_KEY = "_walter_audio_duplicate_suppressed_count"


def completed_scan_token(state: MutableMapping[str, Any]) -> str:
    """Return a stable token for the completed scan currently rendered."""
    try:
        from .completed_scan import completed_scan_for_view

        scan = completed_scan_for_view(state, "GS366 audio delivery")
    except Exception:
        scan = None
    completed_at = getattr(scan, "completed_at", None)
    if isinstance(completed_at, datetime):
        return completed_at.isoformat()
    if completed_at:
        return str(completed_at)
    return "no-completed-scan"


def alert_delivery_signature(
    sound_path: str, phrase: str, voice_name: str = ""
) -> str:
    """Normalize the browser-delivery request without interpreting trade state."""
    normalized_phrase = " ".join(str(phrase or "").split())
    return "|".join(
        (
            str(sound_path or ""),
            str(voice_name or ""),
            normalized_phrase,
        )
    )


def should_deliver_alert(
    state: MutableMapping[str, Any],
    *,
    sound_path: str,
    phrase: str,
    voice_name: str = "",
) -> bool:
    """Allow one delivery per unique alert request within one completed scan."""
    if not phrase:
        return True

    scan_token = completed_scan_token(state)
    if state.get(_SCAN_TOKEN_KEY) != scan_token:
        state[_SCAN_TOKEN_KEY] = scan_token
        state[_DELIVERED_KEY] = set()

    delivered = set(state.get(_DELIVERED_KEY) or set())
    signature = alert_delivery_signature(sound_path, phrase, voice_name)
    if signature in delivered:
        state[_SUPPRESSED_COUNT_KEY] = int(
            state.get(_SUPPRESSED_COUNT_KEY, 0) or 0
        ) + 1
        return False

    delivered.add(signature)
    state[_DELIVERED_KEY] = delivered
    return True


def _inherit(wrapper, wrapped) -> None:
    for name, value in getattr(wrapped, "__dict__", {}).items():
        if name.startswith("_gs") and not hasattr(wrapper, name):
            setattr(wrapper, name, value)


def install() -> None:
    """Install server dedupe, then Walter's final browser audio broker."""
    from . import ui

    current = ui.play_alert
    if not getattr(current, "_gs366_rerun_alert_dedupe", False):
        def play_alert(sound_path: str, phrase: str, voice_name: str = ""):
            if not should_deliver_alert(
                ui.st.session_state,
                sound_path=sound_path,
                phrase=phrase,
                voice_name=voice_name,
            ):
                print(
                    "[WALTER AUDIO] duplicate delivery suppressed for current completed scan",
                    flush=True,
                )
                return None
            return current(sound_path, phrase, voice_name)

        _inherit(play_alert, current)
        play_alert._gs366_rerun_alert_dedupe = True
        play_alert._gs366_original = current
        ui.play_alert = play_alert

    # Always attempt GS367 installation.  On a warm Streamlit deployment the old
    # GS366 wrapper may already be present, so returning early here would prevent
    # the browser broker from ever becoming the final audio layer.
    from .gs367_browser_audio_broker import install as _install_gs367_browser_audio_broker

    _install_gs367_browser_audio_broker()

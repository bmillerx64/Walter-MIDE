"""GS365: prevent negative entry-language from triggering three-chime alerts.

Presentation/audio only. Scanner logic, qualification, readiness, scoring, ranking,
market-data membership, execution, and orders are unchanged.

GS363/GS364 intentionally derive acoustic urgency from the spoken phrase. Live
2026-09-02 evidence exposed a semantic collision: ordinary alerts can contain
phrases such as ``Not yet Entry Ready``. A raw substring search therefore heard
``ENTRY READY`` and emitted the three-chime highest-attention cadence even while
Walter visibly showed DEVELOPING / NO TRADE.

This final audio wrapper preserves GS364's single serial cadence and GS311 speech
transport, but classifies only *affirmative* attention-state language.
"""
from __future__ import annotations

from pathlib import Path


_HIGH_TIER_TOKENS = (
    "WATCH FOR ENTRY",
    "ENTRY READY",
    "ENTRY WINDOW",
    "GET READY",
)
_MID_TIER_TOKENS = ("LOOK NOW", "WATCH NOW")

# Remove explicit negative/closed forms before evaluating affirmative tokens.
# These are operator-language guards, not trading rules.
_NEGATED_PHRASES = (
    "NOT YET ENTRY READY",
    "NOT ENTRY READY",
    "NO ENTRY READY",
    "NOT READY FOR ENTRY",
    "NO ENTRY REVIEW",
    "NO ENTRY WINDOW",
    "ENTRY WINDOW CLOSED",
    "ENTRY WINDOW IS CLOSED",
    "ENTRY WINDOW NOT OPEN",
    "ENTRY WINDOW IS NOT OPEN",
    "ENTRY READY WITHDRAWN",
    "ENTRY READINESS WITHDRAWN",
    "ENTRY READINESS IS WITHDRAWN",
    "NOT YET LOOK NOW",
    "NOT LOOK NOW",
    "NOT YET WATCH NOW",
    "NOT WATCH NOW",
)


def semantic_chime_count(phrase: str) -> int:
    """Return 1/2/3 chimes from affirmative spoken-state semantics only."""
    text = " ".join(str(phrase or "").upper().split())
    if not text:
        return 1

    classified = text
    for negative in _NEGATED_PHRASES:
        classified = classified.replace(negative, " ")

    if any(token in classified for token in _HIGH_TIER_TOKENS):
        return 3
    if any(token in classified for token in _MID_TIER_TOKENS):
        return 2
    return 1


def _inherit(wrapper, wrapped) -> None:
    for name, value in getattr(wrapped, "__dict__", {}).items():
        if name.startswith("_gs") and not hasattr(wrapper, name):
            setattr(wrapper, name, value)


def install() -> None:
    """Replace only GS364's phrase classifier while retaining its audio transport."""
    from . import ui
    from .gs364_live_operator_containment import _exact_chime_markup

    current = ui.play_alert
    if getattr(current, "_gs365_chime_semantics", False):
        return

    # GS364 saved the pre-GS364 alert wrapper here. Calling that wrapper with a
    # deliberately missing WAV keeps speech/diagnostics intact while suppressing
    # both its base chime and GS363's extra-chime component. We then emit exactly
    # one serial cadence with the corrected semantic classifier.
    voice_transport = getattr(current, "_gs364_original", None)
    if not callable(voice_transport):
        return

    def play_alert(sound_path: str, phrase: str, voice_name: str = ""):
        if not phrase:
            return voice_transport(sound_path, phrase, voice_name)

        silent_path = str(Path(sound_path).with_name("__walter_voice_only__.missing"))
        result = voice_transport(silent_path, phrase, voice_name)
        markup = _exact_chime_markup(sound_path, semantic_chime_count(phrase))
        if markup:
            ui.st.components.v1.html(markup, height=0, scrolling=False)
        return result

    _inherit(play_alert, current)
    play_alert._gs365_chime_semantics = True
    play_alert._gs365_original = current
    ui.play_alert = play_alert

"""GS441: make LOOK NOW and entry urgency unmistakable by ear.

Live validation on 2026-09-11 showed that Walter's GS399/GS418 audio tiers are
technically different, but the two/three-note action alerts still belong to the same
short electronic-chime family as the routine scan heartbeat. During active Webull
monitoring that is not enough separation to reliably pull the operator's attention.

GS441 changes only the browser playback signature after GS367 has already selected
the winning semantic tier for a completed scan:

* tier 1 routine heartbeat remains the existing short single sine blip;
* tier 2 LOOK NOW becomes a spaced low/high two-note triangle "attention" signature;
* tier 3 entry urgency becomes a rapid high/low/high three-note square-wave signature.

The semantic classifier, highest-tier broker, scan token, speech, qualification,
Opportunity State truth, market-hours behavior, discovery, data, indicators, scoring,
thresholds, execution, and orders are unchanged. WATCH FOR ENTRY / ENTRY READY /
ENTRY WINDOW remain the existing tier-3 entry-urgency family; this module does not
reclassify phrases or manufacture alerts.
"""
from __future__ import annotations

from functools import wraps


LOOK_NOW_PATTERN = ((640, 0.00), (1280, 0.38))
ENTRY_URGENCY_PATTERN = ((1568, 0.00), (988, 0.12), (1568, 0.24))
LOOK_NOW_WAVE = "triangle"
ENTRY_URGENCY_WAVE = "square"
LOOK_NOW_GAIN = 0.48
ENTRY_URGENCY_GAIN = 0.52
LOOK_NOW_RELEASE_SECONDS = 0.30
ENTRY_URGENCY_RELEASE_SECONDS = 0.10
LOOK_NOW_STOP_SECONDS = 0.32
ENTRY_URGENCY_STOP_SECONDS = 0.12


def _js_pattern(pattern: tuple[tuple[int, float], ...]) -> str:
    return "[" + ",".join(f"[{frequency},{offset:.2f}]" for frequency, offset in pattern) + "]"


def distinct_action_markup(markup: str) -> str:
    """Overlay only tier-2/3 browser acoustics; leave tier 1 and broker truth intact."""
    text = str(markup or "")

    # Override the browser-local patterns after GS367 serializes its historical public
    # tone table. Keeping broker.TONE_PATTERNS untouched preserves older public/test
    # contracts while the final audible result gets the stronger operator signature.
    key_needle = "  const key = '__walterGS367ChimeBroker';"
    if key_needle in text and "GS441: action-only signatures" not in text:
        pattern_overlay = (
            "  // GS441: action-only signatures; tier 1 routine heartbeat is untouched.\n"
            f"  patterns['2'] = {_js_pattern(LOOK_NOW_PATTERN)};\n"
            f"  patterns['3'] = {_js_pattern(ENTRY_URGENCY_PATTERN)};\n"
        )
        text = text.replace(key_needle, pattern_overlay + key_needle, 1)

    # GS399 already made the final winning tier control the envelope. Strengthen that
    # same boundary instead of adding another classifier or competing audio path.
    text = text.replace(
        "oscillator.type = tier === 2 ? 'triangle' : (tier === 3 ? 'sawtooth' : 'sine');",
        "oscillator.type = tier === 2 ? 'triangle' : (tier === 3 ? 'square' : 'sine');",
        1,
    )
    text = text.replace(
        "gain.gain.exponentialRampToValueAtTime(tier === 2 ? 0.42 : (tier === 3 ? 0.46 : 0.24), start + 0.014);",
        "gain.gain.exponentialRampToValueAtTime(tier === 2 ? 0.48 : (tier === 3 ? 0.52 : 0.24), start + 0.014);",
        1,
    )
    text = text.replace(
        "gain.gain.exponentialRampToValueAtTime(0.0001, start + (tier === 2 ? 0.34 : (tier === 3 ? 0.22 : 0.13)));",
        "gain.gain.exponentialRampToValueAtTime(0.0001, start + (tier === 2 ? 0.30 : (tier === 3 ? 0.10 : 0.13)));",
        1,
    )
    text = text.replace(
        "oscillator.stop(start + (tier === 2 ? 0.36 : (tier === 3 ? 0.24 : 0.145)));",
        "oscillator.stop(start + (tier === 2 ? 0.32 : (tier === 3 ? 0.12 : 0.145)));",
        1,
    )
    return text


def _install_gs442() -> None:
    from .gs442_alignment_ladder_truth import install as install_gs442

    install_gs442()


def install() -> None:
    """Install as the final browser-audio presentation wrapper."""
    from . import gs367_browser_audio_broker as broker

    current = broker.browser_broker_markup
    if getattr(current, "_gs441_distinct_action_audio", False):
        # Warm sessions may already own GS441. Still converge the newer final
        # operator-presentation layer without rebinding the audio wrapper.
        _install_gs442()
        return

    @wraps(current)
    def browser_broker_markup(scan_token: str, tier: int) -> str:
        return distinct_action_markup(current(scan_token, tier))

    browser_broker_markup._gs441_distinct_action_audio = True
    browser_broker_markup._gs441_original = current
    broker.browser_broker_markup = browser_broker_markup
    _install_gs442()

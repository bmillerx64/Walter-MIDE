"""GS418: restore the routine one-note scan/watch audio tier.

Live validation on 2026-09-10 confirmed Walter was scanning normally after GS417 but
no longer emitted the familiar one/two/three-note end-of-scan feedback. GS402 had
intentionally consumed tier-1 routine browser audio silently, while tiers 2 and 3
remained audible for LOOK NOW and entry urgency.

The operator contract is restored here: tier 1 = one routine blip, tier 2 = LOOK NOW,
tier 3 = entry urgency. This is audio/presentation only and changes no alert truth,
scan cadence, discovery, market data, scoring, qualification, readiness, thresholds,
execution, or orders.
"""
from __future__ import annotations

from functools import wraps


_GS402_SILENCE = (
    "    // GS402: routine tier remains semantically valid but is acoustically silent.\n"
    "    // LOOK NOW (tier 2) and entry urgency (tier 3) are the only browser tones.\n"
    "    if (tier === 1) return;\n\n"
)


def restore_routine_tier(markup: str) -> str:
    """Remove only GS402's tier-1 early return; preserve every other audio rule."""
    text = str(markup or "")
    if _GS402_SILENCE not in text:
        return text
    return text.replace(
        _GS402_SILENCE,
        "    // GS418: tier 1 is audible again as the routine one-note scan/watch cue.\n\n",
        1,
    )


def install() -> None:
    """Install after GS402 so the final browser broker can emit routine tier 1."""
    from . import gs367_browser_audio_broker as broker

    current = broker.browser_broker_markup
    if getattr(current, "_gs418_restore_routine_scan_audio", False):
        return

    @wraps(current)
    def browser_broker_markup(scan_token: str, tier: int) -> str:
        return restore_routine_tier(current(scan_token, tier))

    browser_broker_markup._gs418_restore_routine_scan_audio = True
    browser_broker_markup._gs418_original = current
    broker.browser_broker_markup = browser_broker_markup

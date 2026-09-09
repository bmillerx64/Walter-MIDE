"""GS402: reserve browser attention tones for LOOK NOW and entry urgency only.

Live 2026-09-09 validation confirmed GS399 made the alert envelopes perceptibly
different, but routine one-note scan/watch sounds still compete for the same auditory
attention. Walter's browser tone should mean one thing: look at the screen now.

GS402 therefore silences only the final broker-selected tier-1 Web Audio tone. Tier 2
LOOK NOW and tier 3 entry urgency keep the distinct GS399 envelopes and GS392 cadence.
Speech, semantic tier assignment, exactly-once scan-token aggregation, discovery,
market data, scoring, qualification, readiness, thresholds, execution, and orders are
unchanged.
"""
from __future__ import annotations

from functools import wraps


ROUTINE_TIER = 1


def _critical_only_markup(markup: str) -> str:
    """Consume routine broker events silently after final tier selection."""
    text = str(markup or "")
    needle = "    broker.tier = 0;\n\n    const AudioContextCtor ="
    replacement = (
        "    broker.tier = 0;\n\n"
        "    // GS402: routine tier remains semantically valid but is acoustically silent.\n"
        "    // LOOK NOW (tier 2) and entry urgency (tier 3) are the only browser tones.\n"
        "    if (tier === 1) return;\n\n"
        "    const AudioContextCtor ="
    )
    if needle in text:
        return text.replace(needle, replacement, 1)
    return text


def install() -> None:
    """Wrap the final browser markup once without changing alert classification."""
    from . import gs367_browser_audio_broker as broker

    current = broker.browser_broker_markup
    if getattr(current, "_gs402_critical_only_audio", False):
        return

    @wraps(current)
    def browser_broker_markup(scan_token: str, tier: int) -> str:
        return _critical_only_markup(current(scan_token, tier))

    browser_broker_markup._gs402_critical_only_audio = True
    browser_broker_markup._gs402_original = current
    broker.browser_broker_markup = browser_broker_markup

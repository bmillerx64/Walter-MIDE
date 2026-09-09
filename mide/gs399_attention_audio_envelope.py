"""GS399: make LOOK NOW acoustically attention-worthy without changing alert truth.

Live 2026-09-09 validation proved GS398 routes genuine LOOK NOW transitions to tier 2,
but the browser still renders every Web Audio note as the same ~130 ms sine-wave blip.
Two tier-2 blips are therefore easy to confuse with routine/tier-3 activity while the
operator is watching Webull.

GS399 is presentation/audio only. It preserves semantic tiers, scan-token aggregation,
exactly-once delivery, speech, discovery, market data, scoring, qualification,
readiness, thresholds, execution, and orders. Only the audible envelope for the tier
that actually wins the GS367 browser broker is changed:

* tier 1 routine: unchanged short sine blip;
* tier 2 LOOK NOW: longer, louder triangle-wave rising pair;
* tier 3 entry urgency: unchanged three short rising sine blips.

The tier-dependent envelope is evaluated against the broker's final winning tier, so
call order between multiple alert registrations in one completed scan cannot apply a
LOOK NOW envelope to a higher-priority tier-3 event.
"""
from __future__ import annotations

from functools import wraps


LOOK_NOW_TIER = 2
LOOK_NOW_WAVE = "triangle"
LOOK_NOW_GAIN = 0.42
LOOK_NOW_RELEASE_SECONDS = 0.34
LOOK_NOW_STOP_SECONDS = 0.36


def _attention_envelope_markup(markup: str) -> str:
    """Make only the final broker-selected tier 2 event materially more salient."""
    text = str(markup or "")
    text = text.replace(
        "oscillator.type = 'sine';",
        "oscillator.type = tier === 2 ? 'triangle' : 'sine';",
    )
    text = text.replace(
        "gain.gain.exponentialRampToValueAtTime(0.24, start + 0.014);",
        "gain.gain.exponentialRampToValueAtTime(tier === 2 ? 0.42 : 0.24, start + 0.014);",
    )
    text = text.replace(
        "gain.gain.exponentialRampToValueAtTime(0.0001, start + 0.13);",
        "gain.gain.exponentialRampToValueAtTime(0.0001, start + (tier === 2 ? 0.34 : 0.13));",
    )
    text = text.replace(
        "oscillator.stop(start + 0.145);",
        "oscillator.stop(start + (tier === 2 ? 0.36 : 0.145));",
    )
    return text


def install() -> None:
    """Wrap the GS367 browser markup generator once, preserving broker semantics."""
    from . import gs367_browser_audio_broker as broker

    current = broker.browser_broker_markup
    if getattr(current, "_gs399_attention_audio_envelope", False):
        return

    @wraps(current)
    def browser_broker_markup(scan_token: str, tier: int) -> str:
        return _attention_envelope_markup(current(scan_token, tier))

    browser_broker_markup._gs399_attention_audio_envelope = True
    browser_broker_markup._gs399_original = current
    broker.browser_broker_markup = browser_broker_markup

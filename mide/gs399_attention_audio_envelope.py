"""GS399: make Walter alert tiers acoustically obvious without changing alert truth.

Live 2026-09-09 validation proved GS398 routes genuine LOOK NOW transitions to tier 2,
but the browser still renders every Web Audio note with the same short sine-wave
blip envelope. In live use, two LOOK NOW blips and three entry-urgency blips remain
too similar to reliably pull operator attention away from Webull.

GS399 is presentation/audio only. It preserves semantic tiers, scan-token aggregation,
exactly-once delivery, speech, discovery, market data, scoring, qualification,
readiness, thresholds, execution, and orders. Only the audible envelope for the tier
that actually wins the GS367 browser broker is changed:

* tier 1 routine: unchanged short sine blip at this layer;
* tier 2 LOOK NOW: longer, louder triangle-wave rising pair;
* tier 3 entry urgency: sharper, louder sawtooth rising triple.

GS402 installs after this layer and may suppress the routine browser tone while leaving
these semantic patterns intact. The tier-dependent envelope is evaluated against the
broker's final winning tier, so call order between multiple alert registrations in one
completed scan cannot apply a lower-priority envelope to a higher-priority event.
"""
from __future__ import annotations

from functools import wraps


LOOK_NOW_TIER = 2
ENTRY_TIER = 3
LOOK_NOW_WAVE = "triangle"
ENTRY_WAVE = "sawtooth"
LOOK_NOW_GAIN = 0.42
ENTRY_GAIN = 0.46
LOOK_NOW_RELEASE_SECONDS = 0.34
ENTRY_RELEASE_SECONDS = 0.22
LOOK_NOW_STOP_SECONDS = 0.36
ENTRY_STOP_SECONDS = 0.24


def _attention_envelope_markup(markup: str) -> str:
    """Make final broker-selected tiers 2 and 3 perceptually distinct from routine."""
    text = str(markup or "")
    text = text.replace(
        "oscillator.type = 'sine';",
        "oscillator.type = tier === 2 ? 'triangle' : (tier === 3 ? 'sawtooth' : 'sine');",
    )
    text = text.replace(
        "gain.gain.exponentialRampToValueAtTime(0.24, start + 0.014);",
        "gain.gain.exponentialRampToValueAtTime(tier === 2 ? 0.42 : (tier === 3 ? 0.46 : 0.24), start + 0.014);",
    )
    text = text.replace(
        "gain.gain.exponentialRampToValueAtTime(0.0001, start + 0.13);",
        "gain.gain.exponentialRampToValueAtTime(0.0001, start + (tier === 2 ? 0.34 : (tier === 3 ? 0.22 : 0.13)));",
    )
    text = text.replace(
        "oscillator.stop(start + 0.145);",
        "oscillator.stop(start + (tier === 2 ? 0.36 : (tier === 3 ? 0.24 : 0.145)));",
    )
    return text


def _install_gs402() -> None:
    from .gs402_critical_only_audio import install as install_gs402

    install_gs402()


def install() -> None:
    """Wrap the GS367 browser markup generator once, preserving broker semantics."""
    from . import gs367_browser_audio_broker as broker

    current = broker.browser_broker_markup
    if getattr(current, "_gs399_attention_audio_envelope", False):
        # Warm Streamlit sessions may already own GS399 while loading newer code.
        _install_gs402()
        return

    @wraps(current)
    def browser_broker_markup(scan_token: str, tier: int) -> str:
        return _attention_envelope_markup(current(scan_token, tier))

    browser_broker_markup._gs399_attention_audio_envelope = True
    browser_broker_markup._gs399_original = current
    broker.browser_broker_markup = browser_broker_markup

    _install_gs402()

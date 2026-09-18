"""GS504: make Walter's action audio categorically different from routine bleeps.

Live validation on 2026-09-18 confirmed the prior GS441 patterns were technically
different but still perceived as the same family of electronic bleeps. Repeated
60-second heartbeat exposure therefore caused operator habituation.

GS504 preserves Walter's existing three semantic tiers, GS367 highest-tier broker,
scan-token aggregation, speech, dedupe, alert truth and all trading authority. It
changes only the final browser synthesis after the broker has already selected the
winning tier:

* tier 1 routine remains the familiar single short blip;
* tier 2 LOOK NOW / runner attention becomes a two-strike harmonic bell signature
  with long decay and a wide gap -- categorically unlike the heartbeat;
* tier 3 WATCH FOR ENTRY / ENTRY READY / ENTRY WINDOW becomes one sustained
  alternating siren sweep -- not a sequence of similar bleeps.

The purpose is human factors, not more alerting: Walter should be able to pull the
operator's eyes back to the screen without manufacturing any additional event.
"""
from __future__ import annotations

from functools import wraps


_OWNER = "_walter_gs504_distinct_attention_alarm"
_MARKER = "GS504: categorical action audio"


def distinct_attention_markup(markup: str) -> str:
    """Replace only tier-2/3 synthesis after GS367 selects the final semantic tier."""
    text = str(markup or "")
    if _MARKER in text:
        return text

    helper_needle = "    const emitPattern = (context) => {"
    if helper_needle not in text:
        return text

    helpers = r"""
    // GS504: categorical action audio.
    // Tier 2 is a harmonic two-strike bell; tier 3 is a sustained alternating siren.
    // Tier 1 intentionally falls through to Walter's existing routine heartbeat.
    const gs504AttentionBell = (context, startBase) => {
      const strike = (start, fundamental) => {
        const frequencies = [
          [fundamental, 0.34],
          [fundamental * 1.5, 0.18],
          [fundamental * 2.01, 0.10],
        ];
        frequencies.forEach(([frequency, peak]) => {
          const oscillator = context.createOscillator();
          const gain = context.createGain();
          oscillator.type = 'sine';
          oscillator.frequency.setValueAtTime(Number(frequency), start);
          gain.gain.setValueAtTime(0.0001, start);
          gain.gain.exponentialRampToValueAtTime(Number(peak), start + 0.018);
          gain.gain.exponentialRampToValueAtTime(0.0001, start + 0.62);
          oscillator.connect(gain);
          gain.connect(context.destination);
          oscillator.start(start);
          oscillator.stop(start + 0.66);
        });
      };
      strike(startBase, 523.25);
      strike(startBase + 0.52, 783.99);
    };

    const gs504UrgentSiren = (context, startBase) => {
      const oscillator = context.createOscillator();
      const harmonic = context.createOscillator();
      const gain = context.createGain();
      const harmonicGain = context.createGain();

      oscillator.type = 'sawtooth';
      harmonic.type = 'sine';
      gain.gain.setValueAtTime(0.0001, startBase);
      harmonicGain.gain.setValueAtTime(0.0001, startBase);
      gain.gain.exponentialRampToValueAtTime(0.30, startBase + 0.025);
      harmonicGain.gain.exponentialRampToValueAtTime(0.12, startBase + 0.025);

      const sweep = [
        [980, 0.00], [1510, 0.16],
        [980, 0.32], [1510, 0.48],
        [980, 0.64], [1510, 0.80],
        [1120, 0.98],
      ];
      sweep.forEach(([frequency, offset], index) => {
        const when = startBase + Number(offset);
        if (index === 0) {
          oscillator.frequency.setValueAtTime(Number(frequency), when);
          harmonic.frequency.setValueAtTime(Number(frequency) * 1.5, when);
        } else {
          oscillator.frequency.linearRampToValueAtTime(Number(frequency), when);
          harmonic.frequency.linearRampToValueAtTime(Number(frequency) * 1.5, when);
        }
      });

      gain.gain.exponentialRampToValueAtTime(0.0001, startBase + 1.08);
      harmonicGain.gain.exponentialRampToValueAtTime(0.0001, startBase + 1.08);
      oscillator.connect(gain);
      harmonic.connect(harmonicGain);
      gain.connect(context.destination);
      harmonicGain.connect(context.destination);
      oscillator.start(startBase);
      harmonic.start(startBase);
      oscillator.stop(startBase + 1.10);
      harmonic.stop(startBase + 1.10);
    };

"""
    text = text.replace(helper_needle, helpers + helper_needle, 1)

    branch_needle = (
        "        const startBase = context.currentTime + 0.035;\n"
        "        const pattern = patterns[String(tier)] || patterns['1'];"
    )
    branch_replacement = (
        "        const startBase = context.currentTime + 0.035;\n"
        "        if (tier === 2) {\n"
        "          gs504AttentionBell(context, startBase);\n"
        "          broker.emittedToken = token;\n"
        "          clearPending();\n"
        "          return true;\n"
        "        }\n"
        "        if (tier === 3) {\n"
        "          gs504UrgentSiren(context, startBase);\n"
        "          broker.emittedToken = token;\n"
        "          clearPending();\n"
        "          return true;\n"
        "        }\n"
        "        const pattern = patterns[String(tier)] || patterns['1'];"
    )
    if branch_needle not in text:
        return text
    return text.replace(branch_needle, branch_replacement, 1)


def _inherit(wrapper, wrapped) -> None:
    for name, value in getattr(wrapped, "__dict__", {}).items():
        if name.startswith("_gs") and not hasattr(wrapper, name):
            setattr(wrapper, name, value)


def install() -> None:
    """Install outside GS441 as the final browser-audio human-factors layer."""
    from . import gs367_browser_audio_broker as broker

    current = broker.browser_broker_markup
    if getattr(current, _OWNER, False):
        return

    @wraps(current)
    def browser_broker_markup(scan_token: str, tier: int) -> str:
        return distinct_attention_markup(current(scan_token, tier))

    _inherit(browser_broker_markup, current)
    browser_broker_markup._gs504_distinct_attention_alarm = True
    browser_broker_markup._gs504_original = current
    setattr(browser_broker_markup, _OWNER, True)
    broker.browser_broker_markup = browser_broker_markup

"""GS367: collapse stacked Walter alert sounds into one browser-scoped cadence.

Audio/presentation only. Scanner membership, market data, scoring, ranking,
qualification, readiness, thresholds, execution, and orders are unchanged.

Live 2026-09-02 evidence showed that Walter can legitimately call ``play_alert``
from more than one alert path in the same completed scan (for example an early
coiling alert plus an opportunity-state alert). Server-side duplicate suppression
cannot collapse those requests because their phrases are different. The browser
therefore receives multiple valid audio components, which can sound like one false
three-chime alert.

GS367 leaves speech and existing server dedupe intact but suppresses every legacy
WAV layer. Each alert request instead registers its semantic urgency with one
parent-window broker keyed by the immutable completed-scan token. The broker waits
a short settle interval, keeps only the highest tier requested for that scan, and
plays one distinct Web Audio pattern exactly once. Streamlit reruns and additional
lower-tier phrases for the same scan cannot add extra sounds afterward.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, MutableMapping


BROKER_SETTLE_MS = 750
TONE_PATTERNS: dict[int, tuple[tuple[int, float], ...]] = {
    1: ((880, 0.00),),
    2: ((880, 0.00), (1175, 0.18)),
    3: ((740, 0.00), (988, 0.16), (1319, 0.32)),
}


def tone_pattern(tier: int) -> tuple[tuple[int, float], ...]:
    """Return Walter's deterministic audible pattern for one urgency tier."""
    normalized = max(1, min(3, int(tier or 1)))
    return TONE_PATTERNS[normalized]


def broker_scan_token(
    state: MutableMapping[str, Any], phrase: str, voice_name: str = ""
) -> str:
    """Return one browser aggregation token for the currently completed scan."""
    from .gs366_rerun_alert_dedupe import completed_scan_token

    token = completed_scan_token(state)
    if token != "no-completed-scan":
        return token
    normalized_phrase = " ".join(str(phrase or "").split())
    return f"no-completed-scan|{voice_name}|{normalized_phrase}"


def browser_broker_markup(scan_token: str, tier: int) -> str:
    """Register one alert with the parent-window highest-tier audio broker."""
    token_json = json.dumps(str(scan_token or "no-completed-scan"))
    requested_tier = max(1, min(3, int(tier or 1)))
    patterns_json = json.dumps(
        {
            str(level): [[frequency, offset] for frequency, offset in pattern]
            for level, pattern in TONE_PATTERNS.items()
        }
    )
    return f"""
<script>
(() => {{
  let host = window;
  try {{ if (window.parent) host = window.parent; }} catch (_) {{ host = window; }}

  const token = {token_json};
  const requestedTier = {requested_tier};
  const patterns = {patterns_json};
  const key = '__walterGS367ChimeBroker';

  let broker = host[key];
  if (!broker || typeof broker !== 'object') {{
    broker = host[key] = {{
      token: null,
      tier: 0,
      timer: null,
      emittedToken: null,
      audioContext: null,
    }};
  }}

  if (broker.emittedToken === token) return;

  if (broker.token !== token) {{
    if (broker.timer) {{
      try {{ host.clearTimeout(broker.timer); }} catch (_) {{}}
    }}
    broker.token = token;
    broker.tier = 0;
    broker.timer = null;
  }}

  broker.tier = Math.max(Number(broker.tier || 0), requestedTier);
  if (broker.timer) {{
    try {{ host.clearTimeout(broker.timer); }} catch (_) {{}}
  }}

  broker.timer = host.setTimeout(() => {{
    broker.timer = null;
    if (broker.emittedToken === token) return;

    const tier = Math.max(1, Math.min(3, Number(broker.tier || 1)));
    broker.emittedToken = token;
    broker.tier = 0;

    const AudioContextCtor =
      host.AudioContext || host.webkitAudioContext ||
      window.AudioContext || window.webkitAudioContext;
    if (!AudioContextCtor) return;

    let context = broker.audioContext;
    try {{
      if (!context || context.state === 'closed') {{
        context = new AudioContextCtor();
        broker.audioContext = context;
      }}
      if (context.state === 'suspended' && context.resume) {{
        const resumed = context.resume();
        if (resumed && resumed.catch) resumed.catch(() => {{}});
      }}

      const startBase = context.currentTime + 0.035;
      const pattern = patterns[String(tier)] || patterns['1'];
      pattern.forEach(([frequency, offset]) => {{
        const start = startBase + Number(offset || 0);
        const oscillator = context.createOscillator();
        const gain = context.createGain();
        oscillator.type = 'sine';
        oscillator.frequency.setValueAtTime(Number(frequency), start);
        gain.gain.setValueAtTime(0.0001, start);
        gain.gain.exponentialRampToValueAtTime(0.24, start + 0.014);
        gain.gain.exponentialRampToValueAtTime(0.0001, start + 0.13);
        oscillator.connect(gain);
        gain.connect(context.destination);
        oscillator.start(start);
        oscillator.stop(start + 0.145);
      }});
    }} catch (_) {{}}
  }}, {BROKER_SETTLE_MS});
}})();
</script>
"""


def _inherit(wrapper, wrapped) -> None:
    for name, value in getattr(wrapped, "__dict__", {}).items():
        if name.startswith("_gs") and not hasattr(wrapper, name):
            setattr(wrapper, name, value)


def install() -> None:
    """Install the browser broker as Walter's final audio-delivery layer."""
    from . import ui
    from .gs365_chime_semantic_classifier import semantic_chime_count

    current = ui.play_alert
    if getattr(current, "_gs367_browser_audio_broker", False):
        return

    def play_alert(sound_path: str, phrase: str, voice_name: str = ""):
        if not phrase:
            return current(sound_path, phrase, voice_name)

        # Preserve GS311 speech plus GS366 server-side dedupe while guaranteeing
        # that no older WAV/chime layer can emit sound beneath the broker.
        silent_path = str(
            Path(sound_path).with_name("__walter_voice_only__.missing")
        )
        result = current(silent_path, phrase, voice_name)

        token = broker_scan_token(ui.st.session_state, phrase, voice_name)
        markup = browser_broker_markup(token, semantic_chime_count(phrase))
        ui.st.components.v1.html(markup, height=0, scrolling=False)
        return result

    _inherit(play_alert, current)
    play_alert._gs367_browser_audio_broker = True
    play_alert._gs367_original = current
    ui.play_alert = play_alert

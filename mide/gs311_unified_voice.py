"""GS311: drive audible attention alerts from Walter's unified display state.

This module is presentation/alert only. It does not change discovery, ranking,
qualification, readiness, thresholds, or execution.
"""
from __future__ import annotations

import base64
import html
import json
from pathlib import Path

from .gs310_unified_opportunity_state import opportunity_state
from .timeframe_alignment import alignment_voice


def unified_state_changes(records: list[dict]) -> list[dict]:
    """Return current unified-opportunity transitions with fresh prior evidence."""
    changes: list[dict] = []
    for record in records:
        previous = record.get("opportunity_pulse_previous") or {}
        if not previous:
            continue
        old = opportunity_state(previous)["state"]
        new = opportunity_state(record)["state"]
        if old == new:
            continue
        changes.append(
            {
                "symbol": str(record.get("symbol") or "").upper(),
                "from": old,
                "to": new,
            }
        )
    return changes


def unified_alert_phrase(records: list[dict]) -> str:
    """Speak the same opportunity-state transition Walter shows visually."""
    changes = unified_state_changes(records)
    if not changes:
        return ""
    first = changes[0]
    record = next(
        (
            item
            for item in records
            if str(item.get("symbol") or "").upper() == first["symbol"]
        ),
        {},
    )
    phrase = f"{first['symbol']}. {first['to']}."
    alignment = alignment_voice(record)
    if alignment:
        phrase += f" {alignment}"
    if len(changes) > 1:
        extra = len(changes) - 1
        phrase += f" {extra} additional opportunity change{'s' if extra != 1 else ''}."
    return phrase


def _speech_component(sound_path: str, phrase: str, voice_name: str = "") -> str:
    """Build browser speech/audio markup using parent speech first, iframe fallback."""
    encoded = ""
    path = Path(sound_path)
    if path.exists():
        encoded = base64.b64encode(path.read_bytes()).decode()
    audio = (
        f'<audio autoplay><source src="data:audio/wav;base64,{encoded}" type="audio/wav"></audio>'
        if encoded
        else ""
    )
    phrase_json = json.dumps(str(phrase))
    voice_json = json.dumps(str(voice_name or ""))
    return f"""
    {audio}
    <script>
    (() => {{
      const phrase = {phrase_json};
      const preferred = {voice_json};
      if (!phrase) return;

      let speechWindow = window;
      try {{
        if (window.parent && 'speechSynthesis' in window.parent) speechWindow = window.parent;
      }} catch (_) {{ speechWindow = window; }}
      if (!('speechSynthesis' in speechWindow)) return;

      const synth = speechWindow.speechSynthesis;
      const Utterance = speechWindow.SpeechSynthesisUtterance || window.SpeechSynthesisUtterance;
      if (!Utterance) return;
      const utterance = new Utterance(phrase);
      utterance.rate = 0.95;
      utterance.pitch = 0.9;
      utterance.volume = 1.0;

      const speak = () => {{
        const voices = synth.getVoices ? synth.getVoices() : [];
        if (preferred && voices.length) {{
          const voice = voices.find(v =>
            v.voiceURI === preferred || v.name === preferred || v.name.includes(preferred)
          );
          if (voice) utterance.voice = voice;
        }}
        synth.speak(utterance);
      }};

      if (synth.getVoices && synth.getVoices().length) {{
        speak();
      }} else {{
        let attempts = 0;
        const retry = () => {{
          attempts += 1;
          if ((synth.getVoices && synth.getVoices().length) || attempts >= 8) {{
            speak();
            return;
          }}
          speechWindow.setTimeout(retry, 125);
        }};
        if ('onvoiceschanged' in synth) synth.onvoiceschanged = speak;
        speechWindow.setTimeout(retry, 125);
      }}
    }})();
    </script>
    """


def install() -> None:
    """Install unified voice semantics before app.py imports UI/escalation helpers."""
    from . import escalation, ui

    escalation.escalation_state_changes = unified_state_changes
    escalation.escalation_alert_phrase = unified_alert_phrase

    def play_alert(sound_path: str, phrase: str, voice_name: str = ""):
        if not phrase:
            return
        ui.st.components.v1.html(
            _speech_component(sound_path, phrase, voice_name),
            height=0,
        )

    play_alert._gs311_unified_voice = True
    ui.play_alert = play_alert

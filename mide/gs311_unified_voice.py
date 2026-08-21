"""GS311/GS317/GS318/GS319: drive audible alerts from Walter's unified display state.

This module is presentation/alert only. It does not change discovery, ranking,
qualification, readiness, thresholds, or execution.
"""
from __future__ import annotations

import base64
import json
from pathlib import Path

from .gs310_unified_opportunity_state import opportunity_state
from .gs318_voice_observability import record_voice_request
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
    """Build resilient browser speech/audio markup with transport diagnostics."""
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
      if (!('speechSynthesis' in speechWindow)) {{
        console.warn('[Walter voice] speechSynthesis unavailable');
        return;
      }}

      const synth = speechWindow.speechSynthesis;
      const Utterance = speechWindow.SpeechSynthesisUtterance || window.SpeechSynthesisUtterance;
      if (!Utterance) {{
        console.warn('[Walter voice] SpeechSynthesisUtterance unavailable');
        return;
      }}

      const utterance = new Utterance(phrase);
      utterance.rate = 0.95;
      utterance.pitch = 0.9;
      utterance.volume = 1.0;
      speechWindow.__walterActiveUtterance = utterance;
      speechWindow.__walterVoiceTransport = {{
        phrase,
        preferred,
        requestedAt: new Date().toISOString(),
        status: 'requested',
      }};

      const release = (status) => {{
        speechWindow.__walterVoiceTransport = {{
          ...speechWindow.__walterVoiceTransport,
          status,
          completedAt: new Date().toISOString(),
        }};
        if (speechWindow.__walterActiveUtterance === utterance) {{
          speechWindow.__walterActiveUtterance = null;
        }}
      }};
      utterance.onstart = () => {{
        speechWindow.__walterVoiceTransport = {{
          ...speechWindow.__walterVoiceTransport,
          status: 'speaking',
          startedAt: new Date().toISOString(),
        }};
        console.info('[Walter voice] speaking', phrase);
      }};
      utterance.onend = () => release('ended');
      utterance.onerror = (event) => {{
        console.warn('[Walter voice] synthesis error', event && event.error ? event.error : event);
        release('error');
      }};

      const chooseVoice = () => {{
        const voices = synth.getVoices ? synth.getVoices() : [];
        if (!preferred || !voices.length) return;
        const preferredLower = preferred.toLowerCase();
        const voice = voices.find(v =>
          v.voiceURI === preferred ||
          v.name === preferred ||
          v.name.toLowerCase().includes(preferredLower)
        );
        if (voice) utterance.voice = voice;
      }};

      let spoken = false;
      const speakOnce = () => {{
        if (spoken) return;
        spoken = true;
        chooseVoice();
        try {{
          if (synth.paused && synth.resume) synth.resume();
          if (synth.cancel) synth.cancel();
          if (synth.resume) synth.resume();
          console.info('[Walter voice] request accepted by component', phrase);
          // Chrome can race a newly queued utterance against the preceding cancel().
          // Give cancellation one event-loop turn to settle before speaking.
          speechWindow.setTimeout(() => {{
            try {{
              synth.speak(utterance);
            }} catch (primaryError) {{
              console.warn('[Walter voice] parent synth failed; using frame fallback', primaryError);
              try {{
                window.speechSynthesis.speak(utterance);
              }} catch (fallbackError) {{
                console.warn('[Walter voice] frame fallback failed', fallbackError);
                release('error');
              }}
            }}
          }}, 75);
        }} catch (setupError) {{
          console.warn('[Walter voice] synth setup failed; using frame fallback', setupError);
          try {{
            window.speechSynthesis.speak(utterance);
          }} catch (fallbackError) {{
            console.warn('[Walter voice] frame fallback failed', fallbackError);
            release('error');
          }}
        }}
      }};

      if (synth.getVoices && synth.getVoices().length) {{
        speakOnce();
      }} else {{
        let attempts = 0;
        const retry = () => {{
          attempts += 1;
          if ((synth.getVoices && synth.getVoices().length) || attempts >= 12) {{
            speakOnce();
            return;
          }}
          speechWindow.setTimeout(retry, 125);
        }};
        if ('onvoiceschanged' in synth) synth.onvoiceschanged = speakOnce;
        speechWindow.setTimeout(retry, 125);
      }}
    }})();
    </script>
    """


def install() -> None:
    """Add unified voice semantics without deleting established alert contracts."""
    from . import escalation, ui

    legacy_state_changes = escalation.escalation_state_changes
    legacy_alert_phrase = escalation.escalation_alert_phrase

    def combined_state_changes(records: list[dict]) -> list[dict]:
        """Preserve first-print/legacy events; otherwise expose unified transitions."""
        legacy = legacy_state_changes(records)
        if legacy:
            return legacy
        return unified_state_changes(records)

    def combined_alert_phrase(records: list[dict]) -> str:
        """Prefer a real unified display transition, then preserve legacy alerts."""
        phrase = unified_alert_phrase(records)
        if phrase:
            return phrase
        return legacy_alert_phrase(records)

    escalation.escalation_state_changes = combined_state_changes
    escalation.escalation_alert_phrase = combined_alert_phrase

    def play_alert(sound_path: str, phrase: str, voice_name: str = ""):
        if not phrase:
            return
        request = None
        try:
            request = record_voice_request(
                ui.st.session_state,
                phrase=str(phrase),
                voice_name=str(voice_name or ""),
            )
        except Exception:
            request = None
        if request:
            print(
                "[WALTER VOICE] request "
                f"#{request['count']} at={request['requested_at']} "
                f"voice={request['voice'] or 'System Default'} phrase={request['phrase']}",
                flush=True,
            )
        ui.st.components.v1.html(
            _speech_component(sound_path, phrase, voice_name),
            height=1,
            scrolling=False,
        )

    play_alert._gs311_unified_voice = True
    play_alert._gs317_voice_transport_hardening = True
    play_alert._gs318_voice_observability = True
    play_alert._gs319_cancel_settle = True
    ui.play_alert = play_alert

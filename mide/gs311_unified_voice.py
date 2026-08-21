"""GS311/GS317/GS318/GS319/GS320/GS321: drive audible alerts from Walter's unified display state.

This module is presentation/alert only. It does not change discovery, ranking,
qualification, readiness, thresholds, or execution.
"""
from __future__ import annotations

import base64
import json
from pathlib import Path

from .gs296_first_print_alert_patch import _explicit_first_observation
from .gs310_unified_opportunity_state import opportunity_state
from .gs318_voice_observability import record_voice_request
from .timeframe_alignment import alignment_voice


FIRST_ATTENTION_STATES = {"LOOK NOW", "WATCH FOR ENTRY", "ENTRY WINDOW"}


def unified_state_changes(records: list[dict]) -> list[dict]:
    """Return current unified-opportunity transitions with fresh prior evidence.

    A proven first observation is also a real transition when Walter's displayed
    state already warrants attention. This keeps voice aligned with the visible
    Opportunity Board without manufacturing repeat alerts from compacted records.
    """
    changes: list[dict] = []
    for record in records:
        symbol = str(record.get("symbol") or "").upper()
        previous = record.get("opportunity_pulse_previous") or {}
        if not previous:
            current_state = opportunity_state(record)["state"]
            if (
                symbol
                and current_state in FIRST_ATTENTION_STATES
                and _explicit_first_observation(record)
            ):
                changes.append(
                    {
                        "symbol": symbol,
                        "from": "NEW",
                        "to": current_state,
                        "event": "first_actionable_attention",
                    }
                )
            continue
        old = opportunity_state(previous)["state"]
        new = opportunity_state(record)["state"]
        if old == new:
            continue
        changes.append(
            {
                "symbol": symbol,
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
    """Build resilient browser speech markup with visible transport diagnostics.

    GS321 keeps the actual browser transport state inside the component instead
    of guessing from the server-side request. The replay button repeats the exact
    same utterance locally, so audio transport can be tested without waiting for
    a market event or creating a second Walter alert event.
    """
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
    <style>
      .walter-voice-diag {{
        box-sizing:border-box; display:flex; align-items:center; gap:8px;
        height:38px; padding:6px 8px; border:1px solid #334155;
        border-radius:8px; background:#0b1119; color:#dbe7f4;
        font:12px -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;
      }}
      .walter-voice-status {{font-weight:800; white-space:nowrap;}}
      .walter-voice-detail {{color:#94a3b8; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; flex:1;}}
      .walter-voice-test {{
        border:1px solid #475569; border-radius:6px; background:#172033;
        color:#f8fafc; padding:3px 7px; cursor:pointer; font-weight:700;
      }}
    </style>
    <div class="walter-voice-diag" role="status" aria-live="polite">
      <span id="walter-voice-status" class="walter-voice-status">Voice: initializing</span>
      <span id="walter-voice-detail" class="walter-voice-detail"></span>
      <button id="walter-voice-test" class="walter-voice-test" type="button">Replay test</button>
    </div>
    {audio}
    <script>
    (() => {{
      const phrase = {phrase_json};
      const preferred = {voice_json};
      const statusNode = document.getElementById('walter-voice-status');
      const detailNode = document.getElementById('walter-voice-detail');
      const replayNode = document.getElementById('walter-voice-test');
      const setStatus = (status, detail = '') => {{
        if (statusNode) statusNode.textContent = `Voice: ${{status}}`;
        if (detailNode) detailNode.textContent = detail;
      }};
      if (!phrase) {{
        setStatus('idle', 'No phrase requested');
        if (replayNode) replayNode.disabled = true;
        return;
      }}

      let speechWindow = window;
      try {{
        if (window.parent && 'speechSynthesis' in window.parent) speechWindow = window.parent;
      }} catch (_) {{ speechWindow = window; }}
      if (!('speechSynthesis' in speechWindow)) {{
        console.warn('[Walter voice] speechSynthesis unavailable');
        setStatus('unavailable', 'Browser Web Speech API is not available');
        return;
      }}

      const synth = speechWindow.speechSynthesis;
      const Utterance = speechWindow.SpeechSynthesisUtterance || window.SpeechSynthesisUtterance;
      if (!Utterance) {{
        console.warn('[Walter voice] SpeechSynthesisUtterance unavailable');
        setStatus('unavailable', 'SpeechSynthesisUtterance is not available');
        return;
      }}

      const resolveVoice = () => {{
        const voices = synth.getVoices ? synth.getVoices() : [];
        if (!preferred || !voices.length) return null;
        const preferredLower = preferred.toLowerCase();
        return voices.find(v =>
          v.voiceURI === preferred ||
          v.name === preferred ||
          v.name.toLowerCase().includes(preferredLower)
        ) || null;
      }};

      const speak = (source) => {{
        const utterance = new Utterance(phrase);
        utterance.rate = 0.95;
        utterance.pitch = 0.9;
        utterance.volume = 1.0;
        const selectedVoice = resolveVoice();
        if (selectedVoice) utterance.voice = selectedVoice;
        const actualVoice = selectedVoice ? selectedVoice.name : (preferred || 'System Default');
        speechWindow.__walterActiveUtterance = utterance;
        speechWindow.__walterVoiceTransport = {{
          phrase,
          preferred,
          actualVoice,
          source,
          requestedAt: new Date().toISOString(),
          status: 'requested',
        }};
        setStatus('requested', `${{actualVoice}} · ${{source}}`);

        const release = (status) => {{
          speechWindow.__walterVoiceTransport = {{
            ...speechWindow.__walterVoiceTransport,
            status,
            completedAt: new Date().toISOString(),
          }};
          setStatus(status, `${{actualVoice}} · ${{source}}`);
          if (speechWindow.__walterActiveUtterance === utterance) {{
            speechWindow.__walterActiveUtterance = null;
          }}
        }};
        const releaseError = (detail) => {{
          // Keep the established GS318 lifecycle contract literal and layer the
          // richer diagnostic detail on top of it instead of changing semantics.
          release('error');
          speechWindow.__walterVoiceTransport = {{
            ...speechWindow.__walterVoiceTransport,
            detail,
          }};
          setStatus('error', detail);
        }};
        utterance.onstart = () => {{
          speechWindow.__walterVoiceTransport = {{
            ...speechWindow.__walterVoiceTransport,
            status: 'speaking',
            startedAt: new Date().toISOString(),
          }};
          setStatus('speaking', `${{actualVoice}} · ${{source}}`);
          console.info('[Walter voice] speaking', phrase);
        }};
        utterance.onend = () => release('ended');
        utterance.onerror = (event) => {{
          const error = event && event.error ? String(event.error) : 'unknown synthesis error';
          console.warn('[Walter voice] synthesis error', error);
          releaseError(error);
        }};

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
                releaseError(String(fallbackError));
              }}
            }}
          }}, 75);
        }} catch (setupError) {{
          console.warn('[Walter voice] synth setup failed; using frame fallback', setupError);
          try {{
            window.speechSynthesis.speak(utterance);
          }} catch (fallbackError) {{
            console.warn('[Walter voice] frame fallback failed', fallbackError);
            releaseError(String(fallbackError));
          }}
        }}
      }};

      let initialSpoken = false;
      const speakInitialOnce = () => {{
        if (initialSpoken) return;
        initialSpoken = true;
        speak('Walter alert');
      }};

      if (replayNode) {{
        replayNode.addEventListener('click', () => speak('manual replay'));
      }}

      if (synth.getVoices && synth.getVoices().length) {{
        speakInitialOnce();
      }} else {{
        let attempts = 0;
        const retry = () => {{
          attempts += 1;
          if ((synth.getVoices && synth.getVoices().length) || attempts >= 12) {{
            speakInitialOnce();
            return;
          }}
          speechWindow.setTimeout(retry, 125);
        }};
        if ('onvoiceschanged' in synth) synth.onvoiceschanged = speakInitialOnce;
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
            height=44,
            scrolling=False,
        )

    play_alert._gs311_unified_voice = True
    play_alert._gs317_voice_transport_hardening = True
    play_alert._gs318_voice_observability = True
    play_alert._gs319_cancel_settle = True
    play_alert._gs320_first_attention = True
    play_alert._gs321_transport_self_test = True
    ui.play_alert = play_alert

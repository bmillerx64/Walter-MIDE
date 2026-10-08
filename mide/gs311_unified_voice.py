"""GS311/GS317/GS318/GS319/GS320/GS321: drive audible alerts from Walter's unified display state.

This module is presentation/alert only. It does not change discovery, ranking,
qualification, readiness, thresholds, or execution.
"""
from __future__ import annotations

import hashlib
import json
from functools import lru_cache
import re
import shutil
import subprocess

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


def _compact_guard_phrase(phrase: str) -> str:
    """Reduce a verbose Walter sentence to the fast operator heads-up."""
    raw = " ".join(str(phrase or "").split()).strip()
    if not raw:
        return ""

    first = raw.split(".", 1)[0].strip().upper()
    symbol = first if re.fullmatch(r"[A-Z][A-Z0-9.-]{0,7}", first) else ""
    if not symbol:
        match = re.match(r"^([A-Z][A-Z0-9.-]{0,7})\\b", raw.upper())
        symbol = match.group(1) if match else ""

    upper = raw.upper()
    states = (
        ("ENTRY READY", "entry ready"),
        ("ENTRY WINDOW", "entry ready"),
        ("LOOK NOW", "look now"),
        ("WATCH FOR ENTRY", "watch for entry"),
        ("IGNITION", "ignition"),
        ("DEVELOPING", "developing"),
        ("PULLBACK", "pullback"),
        ("VWAP RECLAIM", "V wap reclaimed"),
        ("SUPER TREND", "super trend flip"),
        ("SUPERTREND", "super trend flip"),
        ("ACTIVE RUNNER", "active runner"),
        ("BREAKOUT", "breakout"),
        ("CHASE / WAIT", "chase wait"),
        ("CHASE/WAIT", "chase wait"),
    )
    state = next((spoken for needle, spoken in states if needle in upper), "alert")
    if symbol:
        spelled = " ".join(ch for ch in symbol if ch.isalnum())
        return f"{spelled}. {state}."
    return f"Walter. {state}."


@lru_cache(maxsize=256)
def _synthesize_phrase_wav(phrase: str) -> str:
    """Return base64 WAV rendered by the deployment's local eSpeak binary.

    GS653 deliberately moves speech generation out of Chrome SpeechSynthesis.
    The browser only plays ordinary PCM through the already-proven Web Audio path.
    """
    text = str(phrase or "").strip()
    if not text:
        return ""
    binary = shutil.which("espeak-ng") or shutil.which("espeak")
    if not binary:
        return ""
    try:
        result = subprocess.run(
            [
                binary,
                "-v", "en-us",
                "-s", "160",
                "-p", "46",
                "-a", "180",
                "--stdout",
                text,
            ],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=4,
        )
    except Exception:
        return ""
    data = bytes(result.stdout or b"")
    if len(data) < 44:
        return ""
    import base64

    return base64.b64encode(data).decode("ascii")


def _speech_component(sound_path: str, phrase: str, voice_name: str = "") -> str:
    """Publish one deterministic WAV voice request to the persistent Audio Guard.

    There is intentionally no local SpeechSynthesis fallback. GS653 makes one owner
    authoritative so Chrome's hidden speech queue can no longer fight Walter.
    """
    compact = _compact_guard_phrase(phrase)
    audio_base64 = _synthesize_phrase_wav(compact)
    audio_key = hashlib.sha1(compact.encode("utf-8")).hexdigest()[:16] if compact else ""
    phrase_json = json.dumps(compact)
    audio_json = json.dumps(audio_base64)
    key_json = json.dumps(audio_key)
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
    </style>
    <div class="walter-voice-diag" role="status" aria-live="polite">
      <span id="walter-voice-status" class="walter-voice-status">Voice: routing</span>
      <span id="walter-voice-detail" class="walter-voice-detail"></span>
    </div>
    <script>
    (() => {{
      const VERSION = 'GS653';
      const phrase = {phrase_json};
      const audioBase64 = {audio_json};
      const audioKey = {key_json};
      const statusNode = document.getElementById('walter-voice-status');
      const detailNode = document.getElementById('walter-voice-detail');
      const setStatus = (state, detail = '') => {{
        if (statusNode) statusNode.textContent = 'Voice: ' + state;
        if (detailNode) detailNode.textContent = detail;
      }};
      if (!phrase) {{
        setStatus('idle', 'No phrase requested');
        return;
      }}
      if (!audioBase64) {{
        setStatus('unavailable', 'eSpeak voice asset unavailable');
        return;
      }}

      let host = window;
      try {{ if (window.parent) host = window.parent; }} catch (_) {{ host = window; }}
      try {{
        const stamp = Number(
          host.localStorage &&
          host.localStorage.getItem('walterAudioGuardHeartbeat')
        );
        const age = Date.now() - stamp;
        const fresh = Number.isFinite(stamp) && age >= 0 && age < 10000;
        const version = host.localStorage &&
          host.localStorage.getItem('walterAudioGuardVersion');
        const voiceReady = Boolean(
          host.localStorage &&
          host.localStorage.getItem('walterAudioGuardVoiceReady') === '1'
        );
        const GuardChannel = host.BroadcastChannel || window.BroadcastChannel;
        if (!fresh || version !== VERSION || !voiceReady || !GuardChannel) {{
          setStatus('blocked', 'Open / test Audio Guard');
          return;
        }}
        const channel = new GuardChannel('walter-audio-guard-v1');
        channel.postMessage({{
          kind: 'voice_wav',
          phrase,
          audioKey,
          audioBase64,
          requestedAt: new Date().toISOString(),
        }});
        channel.close();
        setStatus('guarded', phrase);
      }} catch (error) {{
        setStatus('error', String(error));
      }}
    }})();
    </script>
    """


_speech_component._gs653_guard_only = True


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
    play_alert._gs322_browser_session_arm = True
    ui.play_alert = play_alert

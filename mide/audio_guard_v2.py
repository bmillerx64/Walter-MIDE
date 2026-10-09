"""GS653: deterministic Web Audio voice guard.

This module replaces the accumulated browser SpeechSynthesis recovery stack with one
transport: server-rendered WAV speech played through the same persistent Web Audio
context that already proves Walter's bell path. Presentation/audio only.
"""
from __future__ import annotations

import json


GUARD_VERSION = "GS653"
CHANNEL_NAME = "walter-audio-guard-v1"
HEARTBEAT_KEY = "walterAudioGuardHeartbeat"
VOICE_READY_KEY = "walterAudioGuardVoiceReady"
BELL_READY_KEY = "walterAudioGuardBellReady"
VERSION_KEY = "walterAudioGuardVersion"
WINDOW_NAME = "walter-audio-guard"


def _ready_wav_base64() -> str:
    from .gs311_unified_voice import _synthesize_phrase_wav

    return _synthesize_phrase_wav("Walter audio ready.")


def alert_audio_health_markup() -> str:
    ready_json = json.dumps(_ready_wav_base64())
    template = r"""
    <style>
      .walter-audio-health {
        display:grid; grid-template-columns:minmax(0,1fr) auto;
        align-items:start; gap:8px;
        border:1px solid #475569; border-radius:8px; padding:7px 8px;
        font:12px -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;
        background:#111827; color:#f8fafc;
      }
      .walter-audio-health.ready { border-color:#22c55e; background:#052e16; }
      .walter-audio-health.warn { border-color:#f59e0b; background:#451a03; }
      .walter-audio-health.bad { border-color:#ef4444; background:#450a0a; }
      .walter-audio-health button {
        border:1px solid #64748b; border-radius:6px; padding:5px 8px;
        background:#172033; color:#f8fafc; cursor:pointer; font-weight:800;
        white-space:nowrap;
      }
      #walter-audio-health-status {
        font-weight:900; line-height:1.25; white-space:normal;
        overflow-wrap:anywhere; min-width:0;
      }
    </style>
    <div id="walter-audio-health" class="walter-audio-health warn">
      <span id="walter-audio-health-status">AUDIO STATUS CHECKING…</span>
      <button id="walter-audio-health-button" type="button">Open / test</button>
    </div>
    <script>
    (() => {
      const VERSION = 'GS653';
      const CHANNEL_NAME = 'walter-audio-guard-v1';
      const HEARTBEAT_KEY = 'walterAudioGuardHeartbeat';
      const VOICE_READY_KEY = 'walterAudioGuardVoiceReady';
      const BELL_READY_KEY = 'walterAudioGuardBellReady';
      const VERSION_KEY = 'walterAudioGuardVersion';
      const WINDOW_NAME = 'walter-audio-guard';
      const READY_WAV = __READY_WAV_JSON__;

      const box = document.getElementById('walter-audio-health');
      const status = document.getElementById('walter-audio-health-status');
      const button = document.getElementById('walter-audio-health-button');
      let root = window;
      try { if (window.parent) root = window.parent; } catch (_) { root = window; }

      const storageGet = (key) => {
        try { return root.localStorage ? root.localStorage.getItem(key) : null; }
        catch (_) { return null; }
      };
      const paint = (kind, text) => {
        if (!box || !status) return;
        box.className = 'walter-audio-health ' + kind;
        status.textContent = text;
      };
      const health = () => {
        const stamp = Number(storageGet(HEARTBEAT_KEY));
        const age = Date.now() - stamp;
        const alive = Number.isFinite(stamp) && age >= 0 && age < 10000;
        const current = storageGet(VERSION_KEY) === VERSION;
        return {
          alive: alive && current,
          staleGeneration: alive && !current,
          voice: alive && current && storageGet(VOICE_READY_KEY) === '1',
          bell: alive && current && storageGet(BELL_READY_KEY) === '1',
        };
      };
      const refresh = () => {
        const h = health();
        if (h.voice && h.bell) {
          paint('ready', 'AUDIO GUARD ACTIVE · WEB AUDIO VOICE + BELL');
          if (button) button.textContent = 'Test / re-arm';
        } else if (h.staleGeneration) {
          paint('warn', 'AUDIO GUARD UPDATE READY · OPEN / TEST');
          if (button) button.textContent = 'Upgrade guard';
        } else if (h.alive && h.bell) {
          paint('warn', 'BELL READY · CLICK GUARD FOR VOICE');
          if (button) button.textContent = 'Open guard';
        } else if (h.alive) {
          paint('warn', 'AUDIO GUARD ALIVE · CLICK ENABLE VOICE + BELL');
          if (button) button.textContent = 'Open guard';
        } else {
          paint('warn', 'AUDIO GUARD OFF · OPEN / TEST ONCE');
          if (button) button.textContent = 'Open / test';
        }
      };

      const launch = () => {
        let guard = null;
        try {
          guard = root.open('', WINDOW_NAME, 'popup=yes,width=410,height=270');
        } catch (_) {
          guard = null;
        }
        if (!guard) {
          paint('bad', 'AUDIO GUARD BLOCKED · ALLOW POP-UPS');
          return;
        }

        try {
          const needsInstall =
            !guard.__walterAudioGuardInstalled ||
            !guard.__walterAudioGuard ||
            guard.__walterAudioGuardVersion !== VERSION;
          if (needsInstall) {
            const doc = guard.document;
            doc.open();
            doc.write(
              '<!doctype html><html><head><title>Walter Audio Guard</title>' +
              '<meta charset="utf-8"><style>' +
              'body{margin:0;padding:18px;background:#07111d;color:#e5eef8;' +
              'font:14px -apple-system,BlinkMacSystemFont,Segoe UI,sans-serif}' +
              'h2{margin:0 0 8px;font-size:18px}#state{color:#fbbf24;font-weight:800;margin-bottom:12px}' +
              'button{border:1px solid #64748b;border-radius:7px;background:#172033;' +
              'color:#f8fafc;padding:8px 12px;cursor:pointer;font-weight:800;margin-bottom:10px}' +
              'p{color:#94a3b8;line-height:1.35}</style></head><body>' +
              '<h2>Walter Audio Guard</h2>' +
              '<div id="state">CLICK ENABLE VOICE + BELL ONCE</div>' +
              '<button id="arm" type="button">Enable voice + bell</button>' +
              '<p>GS653 uses one persistent Web Audio transport for both voice and bell. ' +
              'It does not use Chrome SpeechSynthesis.</p></body></html>'
            );
            doc.close();

            const script = doc.createElement('script');
            script.textContent = `
(() => {
  const VERSION = 'GS653';
  const CHANNEL_NAME = 'walter-audio-guard-v1';
  const HEARTBEAT_KEY = 'walterAudioGuardHeartbeat';
  const VOICE_READY_KEY = 'walterAudioGuardVoiceReady';
  const BELL_READY_KEY = 'walterAudioGuardBellReady';
  const VERSION_KEY = 'walterAudioGuardVersion';
  const READY_WAV = ${JSON.stringify(READY_WAV)};
  const stateNode = document.getElementById('state');
  const armNode = document.getElementById('arm');
  const AudioContextCtor = window.AudioContext || window.webkitAudioContext;

  let context = null;
  let voiceChain = Promise.resolve();
  let lastToneToken = null;
  const bufferCache = new Map();

  const put = (key, value) => {
    try {
      if (value === null) localStorage.removeItem(key);
      else localStorage.setItem(key, String(value));
    } catch (_) {}
  };
  const ready = (key) => {
    try { return localStorage.getItem(key) === '1'; } catch (_) { return false; }
  };
  const heartbeat = () => {
    put(HEARTBEAT_KEY, Date.now());
    put(VERSION_KEY, VERSION);
  };
  const setReady = (voice, bell) => {
    put(VOICE_READY_KEY, voice ? '1' : null);
    put(BELL_READY_KEY, bell ? '1' : null);
  };
  const paint = (text, ok = false) => {
    if (!stateNode) return;
    stateNode.style.color = ok ? '#86efac' : '#fbbf24';
    stateNode.textContent = text;
  };
  const update = (detail = '') => {
    const voice = ready(VOICE_READY_KEY);
    const bell = ready(BELL_READY_KEY);
    if (voice && bell) {
      paint(detail || 'ACTIVE · WEB AUDIO VOICE + BELL', true);
      if (armNode) armNode.textContent = 'Test / re-arm';
    } else if (bell) {
      paint(detail || 'BELL READY · CLICK ENABLE VOICE + BELL');
      if (armNode) armNode.textContent = 'Enable voice + bell';
    } else {
      paint(detail || 'CLICK ENABLE VOICE + BELL ONCE');
      if (armNode) armNode.textContent = 'Enable voice + bell';
    }
  };

  const ensureContext = () => {
    if (!AudioContextCtor) return null;
    if (!context || context.state === 'closed') {
      context = new AudioContextCtor();
      context.onstatechange = () => {
        if (context && context.state === 'running') return;
        put(VOICE_READY_KEY, null);
        put(BELL_READY_KEY, null);
        update('AUDIO PAUSED · CLICK ENABLE VOICE + BELL');
      };
    }
    return context;
  };

  const ensureRunning = async () => {
    const ctx = ensureContext();
    if (!ctx) return null;
    if (ctx.state !== 'running' && ctx.resume) {
      try { await ctx.resume(); } catch (_) {}
    }
    return ctx.state === 'running' ? ctx : null;
  };

  const decode = async (key, base64) => {
    if (!base64) throw new Error('missing voice audio');
    if (bufferCache.has(key)) return bufferCache.get(key);
    const ctx = await ensureRunning();
    if (!ctx) throw new Error('audio context blocked');
    const raw = atob(base64);
    const bytes = new Uint8Array(raw.length);
    for (let i = 0; i < raw.length; i += 1) bytes[i] = raw.charCodeAt(i);
    const buffer = await ctx.decodeAudioData(bytes.buffer.slice(0));
    bufferCache.set(key, buffer);
    return buffer;
  };

  const playBuffer = async (buffer) => {
    const ctx = await ensureRunning();
    if (!ctx) throw new Error('audio context blocked');
    return new Promise((resolve, reject) => {
      try {
        const source = ctx.createBufferSource();
        const gain = ctx.createGain();
        gain.gain.value = 1.0;
        source.buffer = buffer;
        source.connect(gain);
        gain.connect(ctx.destination);
        source.onended = () => resolve();
        source.start(ctx.currentTime + 0.02);
      } catch (error) {
        reject(error);
      }
    });
  };

  const emitTone = async (tier, token, proveReady = false) => {
    if (token && token === lastToneToken) return;
    const ctx = await ensureRunning();
    if (!ctx) {
      if (proveReady) put(BELL_READY_KEY, null);
      update('BELL BLOCKED · CLICK ENABLE VOICE + BELL');
      return;
    }
    try {
      const normalized = Math.max(1, Math.min(3, Number(tier || 1)));
      const patterns = {
        1: [[880, 0.00]],
        2: [[880, 0.00], [1175, 0.18]],
        3: [[740, 0.00], [988, 0.16], [1319, 0.32]],
      };
      const startBase = ctx.currentTime + 0.03;
      (patterns[normalized] || patterns[1]).forEach(([frequency, offset]) => {
        const start = startBase + Number(offset || 0);
        const oscillator = ctx.createOscillator();
        const gain = ctx.createGain();
        oscillator.type = 'sine';
        oscillator.frequency.setValueAtTime(Number(frequency), start);
        gain.gain.setValueAtTime(0.0001, start);
        gain.gain.exponentialRampToValueAtTime(0.22, start + 0.014);
        gain.gain.exponentialRampToValueAtTime(0.0001, start + 0.13);
        oscillator.connect(gain);
        gain.connect(ctx.destination);
        oscillator.start(start);
        oscillator.stop(start + 0.145);
      });
      if (token) lastToneToken = token;
      if (proveReady) put(BELL_READY_KEY, '1');
      update();
    } catch (_) {
      if (proveReady) put(BELL_READY_KEY, null);
      update('BELL ERROR · CLICK ENABLE VOICE + BELL');
    }
  };

  const queueVoice = (audioKey, base64) => {
    if (!ready(VOICE_READY_KEY) || !base64) return;
    voiceChain = voiceChain
      .catch(() => {})
      .then(async () => {
        const buffer = await decode(audioKey || ('voice-' + base64.length), base64);
        paint('ACTIVE · WALTER SPEAKING', true);
        await playBuffer(buffer);
        update();
      })
      .catch(() => {
        put(VOICE_READY_KEY, null);
        update('VOICE PLAYBACK ERROR · CLICK ENABLE VOICE + BELL');
      });
  };

  const arm = async () => {
    heartbeat();
    setReady(false, false);
    update('ARMING WEB AUDIO VOICE + BELL…');
    const ctx = await ensureRunning();
    if (!ctx) {
      update('AUDIO BLOCKED · CLICK ENABLE VOICE + BELL');
      return;
    }
    try {
      const readyBuffer = await decode('ready', READY_WAV);
      put(VOICE_READY_KEY, '1');
      paint('TESTING VOICE…', true);
      await playBuffer(readyBuffer);
      await emitTone(2, 'guard-arm-' + Date.now(), true);
      put(VOICE_READY_KEY, '1');
      put(BELL_READY_KEY, '1');
      update('ACTIVE · WEB AUDIO VOICE + BELL');
    } catch (_) {
      put(VOICE_READY_KEY, null);
      await emitTone(2, 'guard-bell-only-' + Date.now(), true);
      update('VOICE ASSET ERROR · BELL READY');
    }
  };

  // GS659: independent delivery paths share one request identity. The guard
  // discards duplicates and expired messages, never replaying stale speech.
  const VOICE_REQUEST_KEY = 'walterAudioGuardVoiceRequest';
  let lastVoiceRequestId = '';
  const receiveVoice = (data) => {
    if (!data || data.kind !== 'voice_wav') return;
    const id = String(data.requestId || '');
    const stamp = Number(data.requestedAtMs || 0);
    const age = Date.now() - stamp;
    if (!id || id === lastVoiceRequestId || !Number.isFinite(age)
        || age < -2000 || age > 12000) return;
    if (!ready(VOICE_READY_KEY)) return;
    lastVoiceRequestId = id;
    queueVoice(String(data.audioKey || ''), String(data.audioBase64 || ''));
  };
  const channel = new BroadcastChannel(CHANNEL_NAME);
  channel.onmessage = (event) => {
    const data = event && event.data ? event.data : {};
    heartbeat();
    if (data.kind === 'tone') {
      if (ready(BELL_READY_KEY)) emitTone(data.tier, data.token, false);
      return;
    }
    receiveVoice(data);
  };
  window.addEventListener('storage', (event) => {
    if (event.key !== VOICE_REQUEST_KEY || !event.newValue) return;
    try { receiveVoice(JSON.parse(event.newValue)); } catch (_) {}
  });

  if (armNode) armNode.addEventListener('click', arm);
  const timer = window.setInterval(heartbeat, 2500);
  window.__walterAudioGuard = {
    ready: () => ({ voice: ready(VOICE_READY_KEY), bell: ready(BELL_READY_KEY) }),
    refresh: update,
    heartbeat,
  };
  window.__walterAudioGuardInstalled = true;
  window.__walterAudioGuardVersion = VERSION;
  setReady(false, false);
  heartbeat();
  update();

  window.addEventListener('beforeunload', () => {
    window.clearInterval(timer);
    try { channel.close(); } catch (_) {}
    put(HEARTBEAT_KEY, null);
    put(VOICE_READY_KEY, null);
    put(BELL_READY_KEY, null);
    put(VERSION_KEY, null);
  });
})();
`;
            doc.body.appendChild(script);
            guard.__walterAudioGuardInstalled = true;
            guard.__walterAudioGuardVersion = VERSION;
          } else if (
            guard.__walterAudioGuard &&
            typeof guard.__walterAudioGuard.refresh === 'function'
          ) {
            guard.__walterAudioGuard.refresh();
          }
          try { guard.focus(); } catch (_) {}
        } catch (_) {
          paint('bad', 'AUDIO GUARD ERROR · RETRY OPEN / TEST');
        }
        window.setTimeout(refresh, 250);
      };

      if (button) button.addEventListener('click', launch);
      refresh();
      window.setInterval(refresh, 2500);
    })();
    </script>
    """
    return template.replace("__READY_WAV_JSON__", ready_json)


def render_sidebar_audio_health(st_module) -> None:
    """Render the one authoritative GS653 audio transport control."""
    try:
        st_module.components.v1.html(
            alert_audio_health_markup(),
            height=118,
            scrolling=False,
        )
    except Exception:
        pass

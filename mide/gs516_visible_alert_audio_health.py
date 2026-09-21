"""GS516: make browser alert-audio health impossible to miss.

Sep. 21 live validation exposed an operator reliability gap after a Streamlit deploy:
Walter's server-side alert logic remained intact, but Chrome's parent-window AudioContext
had been destroyed. The old sessionStorage "armed" flag survived, while the actual
Web Audio transport was no longer runnable. The existing GS352 control correctly
detects this state, but it lives inside a collapsed Alert transport expander.

GS516 adds one always-visible audio health control that observes the exact same
GS367 parent-window broker and can re-arm/test tone + speech with one user gesture.
GS520 anchors that control directly beside the sidebar audio settings instead of
wrapping Walter's mission renderer.
It polls browser transport state so a stale/reloaded AudioContext turns visibly red.

Presentation/transport only. No alert semantics, tiers, phrases, scanning, market data,
scoring, qualification, ranking, readiness, execution, or orders change.
"""
from __future__ import annotations


_OWNER = "_walter_gs516_visible_alert_audio_health"


def alert_audio_health_markup() -> str:
    return r"""
    <style>
      .walter-audio-health {
        display:flex; align-items:center; justify-content:space-between; gap:8px;
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
      #walter-audio-health-status { font-weight:900; line-height:1.25; }
    </style>
    <div id="walter-audio-health" class="walter-audio-health warn">
      <span id="walter-audio-health-status">AUDIO STATUS CHECKING…</span>
      <button id="walter-audio-health-button" type="button">Re-arm / test</button>
    </div>
    <script>
    (() => {
      const box = document.getElementById('walter-audio-health');
      const status = document.getElementById('walter-audio-health-status');
      const button = document.getElementById('walter-audio-health-button');
      let root = window;
      try { if (window.parent) root = window.parent; } catch (_) { root = window; }

      const brokerKey = '__walterGS367ChimeBroker';
      const ensureBroker = () => {
        let broker = root[brokerKey];
        if (!broker || typeof broker !== 'object') {
          broker = root[brokerKey] = {
            token: null, tier: 0, timer: null, emittedToken: null,
            audioContext: null, pendingToken: null, pendingTier: 0,
            pendingEmit: null, unlockBound: false,
          };
        }
        return broker;
      };
      const readArmed = () => {
        try {
          return Boolean(root.__walterVoiceArmed) ||
            (root.sessionStorage &&
             root.sessionStorage.getItem('walterVoiceArmed') === '1');
        } catch (_) { return false; }
      };
      const markArmed = () => {
        try { root.__walterVoiceArmed = true; } catch (_) {}
        try {
          if (root.sessionStorage) root.sessionStorage.setItem('walterVoiceArmed', '1');
        } catch (_) {}
      };
      const audioReady = () => {
        try {
          const broker = ensureBroker();
          return Boolean(broker.audioContext && broker.audioContext.state === 'running');
        } catch (_) { return false; }
      };
      const paint = (kind, text) => {
        if (!box || !status) return;
        box.className = 'walter-audio-health ' + kind;
        status.textContent = text;
      };
      const refresh = () => {
        if (audioReady()) {
          paint('ready', 'AUDIO READY');
        } else if (readArmed()) {
          paint('bad', 'AUDIO DISARMED AFTER RELOAD · RE-ARM');
        } else {
          paint('warn', 'AUDIO NOT ARMED · RE-ARM');
        }
      };

      const testVoice = () => {
        try {
          const synth = window.speechSynthesis || root.speechSynthesis;
          const Utterance =
            window.SpeechSynthesisUtterance || root.SpeechSynthesisUtterance;
          if (!synth || !Utterance) return;
          const utterance = new Utterance('Walter alerts ready.');
          utterance.rate = 0.95;
          utterance.pitch = 0.9;
          utterance.volume = 1.0;
          synth.speak(utterance);
        } catch (_) {}
      };

      const rearm = () => {
        try {
          const AudioContextCtor =
            root.AudioContext || root.webkitAudioContext ||
            window.AudioContext || window.webkitAudioContext;
          if (!AudioContextCtor) {
            paint('bad', 'WEB AUDIO UNAVAILABLE');
            return;
          }
          const broker = ensureBroker();
          let ctx = broker.audioContext;
          if (!ctx || ctx.state === 'closed') {
            ctx = new AudioContextCtor();
            broker.audioContext = ctx;
          }
          const play = () => {
            if (!ctx || ctx.state !== 'running') {
              paint('bad', 'AUDIO BLOCKED · CLICK AGAIN');
              return;
            }
            const osc = ctx.createOscillator();
            const gain = ctx.createGain();
            gain.gain.value = 0.04;
            osc.frequency.value = 660;
            osc.connect(gain); gain.connect(ctx.destination);
            osc.start();
            osc.stop(ctx.currentTime + 0.10);
            markArmed();
            testVoice();
            paint('ready', 'AUDIO READY · TEST CONFIRMED');
          };
          if (ctx.state === 'running') {
            play();
          } else if (ctx.resume) {
            const resumed = ctx.resume();
            if (resumed && resumed.then) {
              resumed.then(play).catch(() =>
                paint('bad', 'AUDIO BLOCKED · CLICK AGAIN'));
            } else {
              play();
            }
          } else {
            paint('bad', 'AUDIO BLOCKED · CLICK AGAIN');
          }
        } catch (_) {
          paint('bad', 'AUDIO TEST FAILED');
        }
      };

      if (button) button.addEventListener('click', rearm);
      refresh();
      const timer = window.setInterval(refresh, 1000);
      window.addEventListener('beforeunload', () => window.clearInterval(timer));
    })();
    </script>
    """


def render_sidebar_audio_health(st_module) -> None:
    """Render transport health at the sidebar control boundary, never in mission slots."""
    try:
        st_module.components.v1.html(
            alert_audio_health_markup(),
            height=58,
            scrolling=False,
        )
    except Exception:
        # Browser transport controls must never interfere with the Radar itself.
        pass


def install() -> None:
    """Compatibility hook; GS520 renders GS516 directly beside sidebar audio controls."""
    return None

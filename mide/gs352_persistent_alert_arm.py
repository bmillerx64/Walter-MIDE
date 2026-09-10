"""GS352: expose a persistent browser-session alert arm/test control.

Presentation/alert transport only. This does not change discovery, ranking,
qualification, readiness, thresholds, execution, orders, or market-data logic.

GS420 makes the test control arm the same parent-window AudioContext used by GS367.
A Streamlit redeploy can preserve sessionStorage while destroying the old JavaScript
AudioContext, so a stale "armed" flag is no longer treated as proof that tones can run.
"""
from __future__ import annotations


def alert_arm_markup() -> str:
    """Return a compact direct-user-activation control for Chrome audio + speech."""
    return r"""
    <style>
      .walter-alert-arm { display:flex; align-items:center; gap:8px; font:12px -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; color:#dbe7f4; }
      .walter-alert-arm button { border:1px solid #475569; border-radius:6px; background:#172033; color:#f8fafc; padding:5px 9px; cursor:pointer; font-weight:700; }
      .walter-alert-arm span { color:#94a3b8; }
    </style>
    <div class="walter-alert-arm">
      <button id="walter-alert-arm-button" type="button">Enable / test alerts</button>
      <span id="walter-alert-arm-status">Not armed</span>
    </div>
    <script>
    (() => {
      const button = document.getElementById('walter-alert-arm-button');
      const status = document.getElementById('walter-alert-arm-status');
      let root = window;
      try {
        if (window.parent) root = window.parent;
      } catch (_) { root = window; }

      const brokerKey = '__walterGS367ChimeBroker';
      const ensureBroker = () => {
        let broker = root[brokerKey];
        if (!broker || typeof broker !== 'object') {
          broker = root[brokerKey] = {
            token: null,
            tier: 0,
            timer: null,
            emittedToken: null,
            audioContext: null,
            pendingToken: null,
            pendingTier: 0,
            pendingEmit: null,
            unlockBound: false,
          };
        }
        return broker;
      };

      const readArmed = () => {
        try {
          return Boolean(root.__walterVoiceArmed) ||
            (root.sessionStorage && root.sessionStorage.getItem('walterVoiceArmed') === '1');
        } catch (_) { return false; }
      };
      const audioReady = () => {
        try {
          const broker = ensureBroker();
          return Boolean(broker.audioContext && broker.audioContext.state === 'running');
        } catch (_) { return false; }
      };
      const markArmed = () => {
        try { root.__walterVoiceArmed = true; } catch (_) {}
        try {
          if (root.sessionStorage) root.sessionStorage.setItem('walterVoiceArmed', '1');
        } catch (_) {}
      };
      const setStatus = (text) => { if (status) status.textContent = text; };
      if (audioReady()) setStatus('Armed for this browser tab');
      else if (readArmed()) setStatus('Re-test after reload');

      const testTone = () => {
        try {
          const AudioContextCtor =
            root.AudioContext || root.webkitAudioContext ||
            window.AudioContext || window.webkitAudioContext;
          if (!AudioContextCtor) {
            setStatus('Web Audio unavailable');
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
              setStatus('Audio blocked · click again');
              return;
            }
            const osc = ctx.createOscillator();
            const gain = ctx.createGain();
            gain.gain.value = 0.035;
            osc.frequency.value = 660;
            osc.connect(gain); gain.connect(ctx.destination);
            osc.start();
            osc.stop(ctx.currentTime + 0.09);
            markArmed();
            setStatus('Armed · tone confirmed');
          };

          if (ctx.state === 'running') {
            play();
          } else if (ctx.resume) {
            const resumed = ctx.resume();
            if (resumed && resumed.then) {
              resumed.then(play).catch(() => setStatus('Audio blocked · click again'));
            } else {
              play();
            }
          } else {
            setStatus('Audio blocked · click again');
          }
        } catch (_) {
          setStatus('Audio test failed');
        }
      };

      const testVoice = () => {
        const synth = window.speechSynthesis || root.speechSynthesis;
        const Utterance = window.SpeechSynthesisUtterance || root.SpeechSynthesisUtterance;
        if (!synth || !Utterance) {
          setStatus('Speech unavailable in this browser');
          return;
        }
        const utterance = new Utterance('Walter alerts ready.');
        utterance.rate = 0.95;
        utterance.pitch = 0.9;
        utterance.volume = 1.0;
        utterance.onstart = () => { markArmed(); };
        utterance.onend = () => { markArmed(); };
        utterance.onerror = (event) => {
          const detail = event && event.error ? String(event.error) : 'speech error';
          setStatus('Voice error: ' + detail);
        };
        try {
          if (synth.paused && synth.resume) synth.resume();
          synth.speak(utterance);
          markArmed();
        } catch (error) {
          setStatus('Voice error: ' + String(error));
        }
      };

      if (button) button.addEventListener('click', () => {
        // Keep both requests inside the actual user gesture. GS420 primes the same
        // parent-window AudioContext that the automatic GS367 broker later reuses.
        testTone();
        testVoice();
      });
    })();
    </script>
    """


def _inherit(wrapper, wrapped) -> None:
    for name, value in getattr(wrapped, "__dict__", {}).items():
        if name.startswith("_gs") and not hasattr(wrapper, name):
            setattr(wrapper, name, value)


def install() -> None:
    from . import ui

    current = ui.render_walter_mission_control
    if getattr(current, "_gs352_persistent_alert_arm", False):
        return

    def render_with_persistent_alert_arm(records: list[dict]) -> None:
        current(records)
        try:
            with ui.st.sidebar.expander("Alert transport", expanded=False):
                ui.st.caption("Arm once per browser tab so tone and voice are available before the first market alert.")
                ui.st.components.v1.html(alert_arm_markup(), height=42, scrolling=False)
        except Exception:
            # Never let browser alert controls interfere with the Radar itself.
            pass

    _inherit(render_with_persistent_alert_arm, current)
    render_with_persistent_alert_arm._gs352_persistent_alert_arm = True
    ui.render_walter_mission_control = render_with_persistent_alert_arm

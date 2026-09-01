"""GS352: expose a persistent browser-session alert arm/test control.

Presentation/alert transport only. This does not change discovery, ranking,
qualification, readiness, thresholds, execution, orders, or market-data logic.
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

      const readArmed = () => {
        try {
          return Boolean(root.__walterVoiceArmed) ||
            (root.sessionStorage && root.sessionStorage.getItem('walterVoiceArmed') === '1');
        } catch (_) { return false; }
      };
      const markArmed = () => {
        try { root.__walterVoiceArmed = true; } catch (_) {}
        try {
          if (root.sessionStorage) root.sessionStorage.setItem('walterVoiceArmed', '1');
        } catch (_) {}
      };
      const setStatus = (text) => { if (status) status.textContent = text; };
      if (readArmed()) setStatus('Armed for this browser tab');

      const testTone = () => {
        try {
          const AudioContext = window.AudioContext || window.webkitAudioContext;
          if (!AudioContext) return;
          const ctx = new AudioContext();
          const osc = ctx.createOscillator();
          const gain = ctx.createGain();
          gain.gain.value = 0.035;
          osc.frequency.value = 660;
          osc.connect(gain); gain.connect(ctx.destination);
          osc.start();
          osc.stop(ctx.currentTime + 0.09);
        } catch (_) {}
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
        utterance.onstart = () => { markArmed(); setStatus('Armed · voice confirmed'); };
        utterance.onend = () => { markArmed(); setStatus('Armed for this browser tab'); };
        utterance.onerror = (event) => {
          const detail = event && event.error ? String(event.error) : 'speech error';
          setStatus('Voice error: ' + detail);
        };
        try {
          if (synth.paused && synth.resume) synth.resume();
          synth.speak(utterance);
          markArmed();
          setStatus('Armed · test requested');
        } catch (error) {
          setStatus('Voice error: ' + String(error));
        }
      };

      if (button) button.addEventListener('click', () => {
        // Keep both requests inside the actual user gesture. This is the most
        // reliable Chrome path for unlocking Web Audio and Web Speech.
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

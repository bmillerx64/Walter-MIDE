"""GS323/GS324: preserve Chrome user activation and stop self-cancelling voice.

Presentation/alert transport only. No discovery, scoring, qualification,
readiness, ranking, thresholds, execution, news, or candidate selection changes.
"""
from __future__ import annotations


def install() -> None:
    """Make Walter speech deterministic without cancelling its own utterances.

    GS323 keeps the first Enable voice click inside the activated frame. GS324
    removes ``speechSynthesis.cancel()`` from the remaining automatic/replay
    transport after deployed Chrome diagnostics proved that path transitions
    from ``requested`` directly to ``error: interrupted``. Browser speech
    synthesis already provides a queue; Walter should enqueue, not cancel, its
    own alerts.
    """
    from . import gs311_unified_voice as voice

    prior_component = voice._speech_component
    if getattr(prior_component, "_gs324_no_self_cancel", False):
        return

    def direct_activation_component(
        sound_path: str, phrase: str, voice_name: str = ""
    ) -> str:
        markup = prior_component(sound_path, phrase, voice_name)

        markup = markup.replace(
            "const speak = (source) => {\n        const utterance = new Utterance(phrase);",
            "const speak = (source, directUserActivation = false) => {\n"
            "        const ActiveUtterance = directUserActivation && window.SpeechSynthesisUtterance\n"
            "          ? window.SpeechSynthesisUtterance\n"
            "          : Utterance;\n"
            "        const utterance = new ActiveUtterance(phrase);",
        )

        normal_transport = """        try {
          if (synth.paused && synth.resume) synth.resume();
          if (synth.cancel) synth.cancel();
          if (synth.resume) synth.resume();
          console.info('[Walter voice] request accepted by component', phrase);"""
        direct_transport = """        if (directUserActivation) {
          // GS323: stay inside the click handler. Do not cancel and do not defer.
          // The activation happened in this Streamlit iframe, so use its synth.
          const activatedSynth = window.speechSynthesis || synth;
          try {
            if (activatedSynth.paused && activatedSynth.resume) activatedSynth.resume();
            console.info('[Walter voice] direct user-activation request', phrase);
            activatedSynth.speak(utterance);
          } catch (activationError) {
            console.warn('[Walter voice] direct activation failed', activationError);
            releaseError(String(activationError));
          }
          return;
        }

        try {
          if (synth.paused && synth.resume) synth.resume();
          if (synth.resume) synth.resume();
          console.info('[Walter voice] request accepted by component', phrase);"""
        markup = markup.replace(normal_transport, direct_transport)

        markup = markup.replace(
            """        if (!isArmed()) {
          markArmed();
          setStatus('requested', 'user activation · pending alert');
          speak('manual replay');
          return;
        }""",
            """        if (!isArmed()) {
          setStatus('requested', 'user activation · pending alert');
          speak('manual activation', true);
          return;
        }""",
        )

        # GS324 safety net: if upstream transport text changes while retaining
        # the old cancel call, strip it from the rendered browser component.
        markup = markup.replace(
            "          if (synth.cancel) synth.cancel();\n",
            "          // GS324: preserve the browser speech queue; do not self-cancel.\n",
        )
        return markup

    direct_activation_component._gs323_direct_user_activation = True
    direct_activation_component._gs324_no_self_cancel = True
    voice._speech_component = direct_activation_component

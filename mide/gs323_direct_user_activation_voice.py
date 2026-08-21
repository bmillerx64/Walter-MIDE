"""GS323: preserve Chrome user activation for Walter's one-time voice arm.

Presentation/alert transport only. No discovery, scoring, qualification,
readiness, ranking, thresholds, execution, news, or candidate selection changes.
"""
from __future__ import annotations


def install() -> None:
    """Make the Enable voice click speak immediately in the activated frame.

    GS322 correctly requires a one-time gesture, but its shared transport still
    cancels synthesis and defers speak() by 75ms. Chrome can report that path as
    ``interrupted`` and the delay needlessly moves the actual speech request away
    from the click that granted transient user activation.

    Keep the established cancel/settle transport for later automatic alerts and
    manual replays. Only the first explicit activation click uses the direct path.
    """
    from . import gs311_unified_voice as voice

    prior_component = voice._speech_component
    if getattr(prior_component, "_gs323_direct_user_activation", False):
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
          if (synth.cancel) synth.cancel();
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

        return markup

    direct_activation_component._gs323_direct_user_activation = True
    voice._speech_component = direct_activation_component

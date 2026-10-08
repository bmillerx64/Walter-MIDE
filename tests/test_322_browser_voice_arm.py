from mide.gs311_unified_voice import _speech_component


def test_gs653_voice_arm_truth_lives_in_audio_guard_not_streamlit_iframe():
    markup = _speech_component("missing-alert.wav", "TEST. LOOK NOW.")
    assert "walterAudioGuardVoiceReady" in markup
    assert "walterAudioGuardHeartbeat" in markup
    assert "walterAudioGuardVersion" in markup
    assert "walterVoiceArmed" not in markup
    assert "sessionStorage" not in markup


def test_gs653_unarmed_transport_does_not_attempt_local_autospeech():
    markup = _speech_component("missing-alert.wav", "TEST. WATCH FOR ENTRY.")
    assert "Open / test Audio Guard" in markup
    assert "speechSynthesis" not in markup
    assert "synth.speak" not in markup


def test_gs653_alert_component_is_publish_only():
    markup = _speech_component("missing-alert.wav", "TEST. ENTRY WINDOW.")
    assert "new GuardChannel('walter-audio-guard-v1')" in markup
    assert "kind: 'voice_wav'" in markup
    assert "channel.postMessage" in markup
    assert "button" not in markup

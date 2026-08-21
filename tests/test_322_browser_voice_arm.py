from mide.gs311_unified_voice import _speech_component


def test_voice_transport_persists_browser_session_arm_state():
    markup = _speech_component("missing-alert.wav", "TEST. LOOK NOW.")

    assert "walterVoiceArmed" in markup
    assert "sessionStorage.getItem('walterVoiceArmed') === '1'" in markup
    assert "sessionStorage.setItem('walterVoiceArmed', '1')" in markup
    assert "__walterVoiceArmed" in markup


def test_unarmed_transport_blocks_autospeech_and_exposes_enable_control():
    markup = _speech_component("missing-alert.wav", "TEST. WATCH FOR ENTRY.")

    assert "if (!isArmed())" in markup
    assert "status: 'blocked'" in markup
    assert "user activation required" in markup
    assert "Click Enable voice once" in markup
    assert "replayNode.textContent = 'Enable voice'" in markup
    assert "blocked pending user activation" in markup


def test_enable_click_speaks_pending_phrase_without_new_server_alert():
    markup = _speech_component("missing-alert.wav", "TEST. ENTRY WINDOW.")

    assert "const manualReplayOrArm = () =>" in markup
    assert "markArmed();" in markup
    assert "speak('manual replay')" in markup
    assert "replayNode.addEventListener('click', manualReplayOrArm)" in markup


def test_successful_speech_confirms_arm_and_retains_gs321_diagnostics():
    markup = _speech_component("missing-alert.wav", "TEST. LOOK NOW.", "Samantha")

    assert "utterance.onstart = () =>" in markup
    assert "markArmed();" in markup
    assert "setStatus('speaking'" in markup
    assert "Replay test" in markup
    assert "actualVoice" in markup
    assert "status: 'speaking'" in markup


def test_armed_path_preserves_settle_and_fallback_without_self_cancellation():
    markup = _speech_component("missing-alert.wav", "TEST. LOOK NOW.")

    assert "synth.cancel()" not in markup
    assert "speechWindow.setTimeout(() =>" in markup
    assert "}, 75);" in markup
    assert "synth.speak(utterance)" in markup
    assert "window.speechSynthesis.speak(utterance)" in markup
    assert "release('error'" in markup

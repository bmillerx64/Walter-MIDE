from mide.gs311_unified_voice import _speech_component


def test_enable_voice_uses_direct_uncancelled_click_transport():
    markup = _speech_component("missing-alert.wav", "TEST. LOOK NOW.")

    assert "directUserActivation = false" in markup
    assert "speak('manual activation', true)" in markup
    assert "const activatedSynth = window.speechSynthesis || synth" in markup
    assert "activatedSynth.speak(utterance)" in markup
    assert "direct user-activation request" in markup


def test_enable_voice_does_not_prearm_before_browser_confirms_start():
    markup = _speech_component("missing-alert.wav", "TEST. LOOK NOW.")

    manual_start = markup.index("const manualReplayOrArm")
    manual_end = markup.index("if (replayNode)", manual_start)
    manual_block = markup[manual_start:manual_end]

    assert "markArmed();" not in manual_block
    assert "speak('manual activation', true)" in manual_block
    assert "utterance.onstart" in markup
    assert "markArmed();" in markup[markup.index("utterance.onstart"):]


def test_direct_activation_path_preserves_transient_user_gesture():
    markup = _speech_component("missing-alert.wav", "TEST. LOOK NOW.")

    direct_start = markup.index("if (directUserActivation)")
    direct_end = markup.index("return;", direct_start)
    direct_block = markup[direct_start:direct_end]

    assert "synth.cancel()" not in direct_block
    assert "setTimeout" not in direct_block
    assert "activatedSynth.speak(utterance)" in direct_block


def test_later_automatic_alerts_preserve_queue_instead_of_self_cancelling():
    markup = _speech_component("missing-alert.wav", "TEST. WATCH FOR ENTRY.")

    assert "synth.cancel()" not in markup
    assert "speechWindow.setTimeout(() =>" in markup
    assert "}, 75);" in markup
    assert "speakInitialOnce();" in markup
    assert "synth.speak(utterance)" in markup


def test_gs322_blocked_and_enable_voice_contract_is_preserved():
    markup = _speech_component("missing-alert.wav", "TEST. LOOK NOW.")

    assert "status: 'blocked'" in markup
    assert "Click Enable voice once" in markup
    assert "replayNode.textContent = 'Enable voice'" in markup
    assert "sessionStorage.getItem('walterVoiceArmed')" in markup

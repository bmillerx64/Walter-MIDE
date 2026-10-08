from mide.gs516_visible_alert_audio_health import alert_audio_health_markup


def test_gs648_speech_queue_watchdog_is_retired_by_gs653():
    markup = alert_audio_health_markup()
    assert "voiceQueue" not in markup
    assert "SpeechSynthesisUtterance" not in markup
    assert "speechSynthesis" not in markup
    assert "let voiceChain = Promise.resolve();" in markup
    assert "kind === 'voice_wav'" in markup


def test_gs653_audio_failure_truth_cannot_stay_false_green():
    markup = alert_audio_health_markup()
    assert "VOICE PLAYBACK ERROR · CLICK ENABLE VOICE + BELL" in markup
    assert "put(VOICE_READY_KEY, null);" in markup
    assert "context.onstatechange" in markup

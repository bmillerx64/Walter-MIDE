from mide.gs516_visible_alert_audio_health import alert_audio_health_markup


def test_gs649_completion_watchdog_is_unnecessary_after_wav_transport():
    markup = alert_audio_health_markup()
    assert "voiceCompletionWatchdog" not in markup
    assert "watchForCompletion" not in markup
    assert "utterance.onend" not in markup
    assert "source.onended = () => resolve();" in markup


def test_gs653_voice_serialization_recovers_after_rejected_job():
    markup = alert_audio_health_markup()
    assert "voiceChain = voiceChain" in markup
    assert ".catch(() => {})" in markup
    assert "await playBuffer(buffer)" in markup

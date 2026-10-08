from mide.gs516_visible_alert_audio_health import alert_audio_health_markup


def test_gs651_prestart_speaking_limbo_is_eliminated_not_retried():
    markup = alert_audio_health_markup()
    assert "watchForStart" not in markup
    assert "synth.speaking" not in markup
    assert "synth.cancel" not in markup
    assert "decodeAudioData" in markup
    assert "createBufferSource" in markup


def test_gs653_guard_popup_generation_is_current():
    markup = alert_audio_health_markup()
    assert "GS653" in markup
    assert "window.__walterAudioGuardVersion = VERSION;" in markup

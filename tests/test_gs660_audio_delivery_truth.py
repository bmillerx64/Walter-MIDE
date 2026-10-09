"""GS660: guard readiness and real alert delivery are distinct facts."""
from mide import audio_guard_v2
from mide import gs311_unified_voice


def test_alert_publisher_records_real_request_time():
    markup = gs311_unified_voice._speech_component('', 'TEST. LOOK NOW.')
    assert "walterAudioGuardVoiceRequestedAt" in markup
    assert "walterAudioGuardVoiceRequest" in markup


def test_guard_reports_independent_receive_and_playback_truth():
    markup = audio_guard_v2.alert_audio_health_markup()
    assert "walterAudioGuardVoiceReceivedAt" in markup
    assert "walterAudioGuardVoicePlayedAt" in markup
    assert "alert requested " in markup
    assert " · received " in markup
    assert " · played " in markup
    assert "await playBuffer(buffer)" in markup
    assert "put('walterAudioGuardVoicePlayedAt', String(Date.now()))" in markup

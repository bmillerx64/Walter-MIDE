"""GS659 regression: short-lived alert delivery survives ephemeral renderers."""
from mide import audio_guard_v2
from mide import gs311_unified_voice as voice


def test_voice_publisher_uses_storage_and_broadcast():
    markup = voice._speech_component("", "ABCD. LOOK NOW.")
    assert "walterAudioGuardVoiceRequest" in markup
    assert "localStorage.setItem" in markup
    assert "channel.postMessage(request)" in markup
    assert "requestId" in markup
    assert "requestedAtMs" in markup


def test_guard_accepts_storage_with_expiry_and_dedupe():
    markup = audio_guard_v2.alert_audio_health_markup()
    assert "event.key !== VOICE_REQUEST_KEY" in markup
    assert "receiveVoice(JSON.parse(event.newValue))" in markup
    assert "id === lastVoiceRequestId" in markup
    assert "age > 12000" in markup
    assert "queueVoice(" in markup


def test_no_scanner_or_alert_eligibility_changes_in_gs659():
    import inspect
    publisher = inspect.getsource(voice._speech_component)
    guard = inspect.getsource(audio_guard_v2.alert_audio_health_markup)
    assert "opportunity_state(" not in publisher
    assert "opportunity_state(" not in guard

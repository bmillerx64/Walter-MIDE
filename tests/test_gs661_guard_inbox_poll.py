"""GS661: persistent audio guard recovers missed iframe events."""
from mide.audio_guard_v2 import alert_audio_health_markup


def test_guard_polls_durable_voice_inbox_and_keeps_dedup_expiry():
    markup = alert_audio_health_markup()
    assert "window.setInterval(pollVoiceInbox, 1000)" in markup
    assert "localStorage.getItem(VOICE_REQUEST_KEY)" in markup
    assert "receiveVoice(JSON.parse(raw))" in markup
    assert "id === lastVoiceRequestId" in markup
    assert "age > 12000" in markup
    assert "window.clearInterval(inboxTimer)" in markup

"""Guard code generations must advance when persistent popup implementation changes."""
from mide import audio_guard_v2, gs311_unified_voice


def test_guard_and_publisher_versions_match_and_upgrade():
    markup = audio_guard_v2.alert_audio_health_markup()
    publisher = gs311_unified_voice._speech_component("", "ABCD. LOOK NOW.")
    assert "const VERSION = 'GS662'" in markup
    assert "const VERSION = 'GS662'" in publisher
    assert 'guard.__walterAudioGuardVersion !== VERSION' in markup
    assert 'window.setInterval(pollVoiceInbox, 1000)' in markup

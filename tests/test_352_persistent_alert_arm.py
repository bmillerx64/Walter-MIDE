from mide.gs352_persistent_alert_arm import alert_arm_markup


def test_alert_arm_requires_direct_user_gesture_and_persists_tab_state():
    markup = alert_arm_markup()
    assert "Enable / test alerts" in markup
    assert "walterVoiceArmed" in markup
    assert "sessionStorage" in markup
    assert "testTone();" in markup
    assert "testVoice();" in markup
    assert "Walter alerts ready." in markup
    assert "button.addEventListener('click'" in markup


def test_alert_arm_does_not_cancel_existing_speech_queue():
    markup = alert_arm_markup()
    assert "synth.cancel" not in markup

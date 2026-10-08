from pathlib import Path

from mide.gs516_visible_alert_audio_health import alert_audio_health_markup


def test_gs652_cancel_speak_failure_mode_is_removed_by_gs653():
    markup = alert_audio_health_markup()
    assert "speechSynthesis" not in markup
    assert "synth.cancel" not in markup
    assert "synth.speak" not in markup


def test_gs653_direct_arm_uses_same_web_audio_path_as_live_voice():
    markup = alert_audio_health_markup()
    arm_start = markup.index("const arm = async () => {")
    arm_end = markup.index("const channel = new BroadcastChannel", arm_start)
    arm = markup[arm_start:arm_end]
    assert "await decode('ready', READY_WAV)" in arm
    assert "await playBuffer(readyBuffer)" in arm
    assert "await emitTone(" in arm


def test_gs653_runtime_removes_legacy_gs352_speech_arm_installer():
    source = Path("mide/__init__.py").read_text(encoding="utf-8")
    assert "_install_gs352_persistent_alert_arm" not in source

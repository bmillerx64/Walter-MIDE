from pathlib import Path

from mide.gs311_unified_voice import _speech_component


def test_gs653_retires_direct_browser_speech_activation_path():
    markup = _speech_component("missing-alert.wav", "TEST. LOOK NOW.")
    assert "speechSynthesis" not in markup
    assert "SpeechSynthesisUtterance" not in markup
    assert "directUserActivation" not in markup
    assert "manual replay" not in markup


def test_gs653_runtime_no_longer_installs_gs323_patch_layer():
    source = Path("mide/__init__.py").read_text(encoding="utf-8")
    assert "_install_gs323_direct_user_activation_voice" not in source


def test_gs653_voice_is_single_owner_guard_transport():
    markup = _speech_component("missing-alert.wav", "TEST. LOOK NOW.")
    assert "kind: 'voice_wav'" in markup
    assert "version !== VERSION" in markup
    assert "voiceReady" in markup

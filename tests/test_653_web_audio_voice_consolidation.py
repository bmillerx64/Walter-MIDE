from pathlib import Path
from types import SimpleNamespace
import base64

from mide import gs311_unified_voice as voice
from mide.audio_guard_v2 import alert_audio_health_markup


def test_gs653_espeak_renderer_returns_cached_base64_wav(monkeypatch):
    voice._synthesize_phrase_wav.cache_clear()
    calls = []

    monkeypatch.setattr(voice.shutil, "which", lambda name: "/usr/bin/espeak" if name == "espeak" else None)

    def fake_run(args, **kwargs):
        calls.append((args, kwargs))
        return SimpleNamespace(stdout=b"RIFF" + b"\x00" * 64)

    monkeypatch.setattr(voice.subprocess, "run", fake_run)

    first = voice._synthesize_phrase_wav("J Z. look now.")
    second = voice._synthesize_phrase_wav("J Z. look now.")

    assert first == second
    assert base64.b64decode(first).startswith(b"RIFF")
    assert len(calls) == 1
    assert "--stdout" in calls[0][0]
    voice._synthesize_phrase_wav.cache_clear()


def test_gs653_live_alert_markup_contains_audio_payload_handoff(monkeypatch):
    monkeypatch.setattr(
        voice,
        "_synthesize_phrase_wav",
        lambda phrase: base64.b64encode(b"RIFF" + b"\x00" * 64).decode("ascii"),
    )
    markup = voice._speech_component("", "JZ. LOOK NOW.")
    assert "Ticker J. Z. look now." in markup
    assert "kind: 'voice_wav'" in markup
    assert "audioBase64" in markup
    assert "speechSynthesis" not in markup


def test_gs653_guard_reuses_one_web_audio_engine_for_both_channels():
    markup = alert_audio_health_markup()
    assert "const ensureContext = () => {" in markup
    assert "createBufferSource" in markup
    assert "createOscillator" in markup
    assert "const channel = new BroadcastChannel(CHANNEL_NAME)" in markup
    assert "data.kind === 'voice_wav'" in markup
    assert "data.kind === 'tone'" in markup


def test_gs653_active_runtime_removes_legacy_browser_speech_patch_layers():
    init = Path("mide/__init__.py").read_text(encoding="utf-8")
    assert "_install_gs323_direct_user_activation_voice" not in init
    assert "_install_gs352_persistent_alert_arm" not in init

    guard = Path("mide/audio_guard_v2.py").read_text(encoding="utf-8")
    voice_source = Path("mide/gs311_unified_voice.py").read_text(encoding="utf-8")
    assert "speechSynthesis" not in guard
    assert "speechSynthesis" not in voice_source


def test_gs653_deployment_installs_espeak_package():
    packages = Path("packages.txt").read_text(encoding="utf-8")
    assert packages.strip() == "espeak"

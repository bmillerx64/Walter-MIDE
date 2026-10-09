from pathlib import Path

from mide.gs516_visible_alert_audio_health import alert_audio_health_markup


def test_gs653_health_exposes_one_named_persistent_audio_guard():
    markup = alert_audio_health_markup()
    assert "walter-audio-guard-v1" in markup
    assert "walter-audio-guard" in markup
    assert "root.open('', WINDOW_NAME" in markup
    assert "Walter Audio Guard" in markup
    assert "AUDIO GUARD ACTIVE · WEB AUDIO VOICE + BELL" in markup
    assert "GS662" in markup


def test_gs653_guard_uses_one_web_audio_context_for_voice_and_bell():
    markup = alert_audio_health_markup()
    start = markup.index("script.textContent =")
    end = markup.index("doc.body.appendChild(script);", start)
    block = markup[start:end]

    assert "AudioContextCtor" in block
    assert "decodeAudioData" in block
    assert "createBufferSource" in block
    assert "createOscillator" in block
    assert "queueVoice" in block
    assert "emitTone" in block
    assert "kind === 'voice_wav'" in block
    assert "kind === 'tone'" in block


def test_gs653_guard_has_no_chrome_speech_synthesis_dependency():
    markup = alert_audio_health_markup()
    assert "speechSynthesis" not in markup
    assert "SpeechSynthesisUtterance" not in markup
    assert "synth.cancel" not in markup
    assert "synth.speak" not in markup
    assert "utterance.onstart" not in markup


def test_gs653_guard_requires_current_generation_and_real_readiness():
    markup = alert_audio_health_markup()
    assert "walterAudioGuardVersion" in markup
    assert "storageGet(VERSION_KEY) === VERSION" in markup
    assert "walterAudioGuardVoiceReady" in markup
    assert "walterAudioGuardBellReady" in markup
    assert "voice: alive && current" in markup
    assert "bell: alive && current" in markup
    assert "AUDIO GUARD UPDATE READY · OPEN / TEST" in markup


def test_gs653_direct_click_proves_exact_voice_playback_path_then_bell():
    markup = alert_audio_health_markup()
    start = markup.index("const arm = async () => {")
    end = markup.index("const channel = new BroadcastChannel", start)
    block = markup[start:end]

    assert "await ensureRunning()" in block
    assert "await decode('ready', READY_WAV)" in block
    assert "await playBuffer(readyBuffer)" in block
    assert "await emitTone(2, 'guard-arm-' + Date.now(), true)" in block
    assert block.index("await playBuffer(readyBuffer)") < block.index("await emitTone(")


def test_gs653_voice_queue_serializes_wav_buffers_without_browser_queue():
    markup = alert_audio_health_markup()
    assert "let voiceChain = Promise.resolve();" in markup
    assert "voiceChain = voiceChain" in markup
    assert ".then(async () => {" in markup
    assert "await playBuffer(buffer)" in markup
    assert "VOICE PLAYBACK ERROR · CLICK ENABLE VOICE + BELL" in markup


def test_gs653_context_loss_clears_truth_instead_of_false_green():
    markup = alert_audio_health_markup()
    assert "context.onstatechange = () => {" in markup
    assert "AUDIO PAUSED · CLICK ENABLE VOICE + BELL" in markup
    assert "put(VOICE_READY_KEY, null);" in markup
    assert "put(BELL_READY_KEY, null);" in markup


def test_visible_audio_health_poll_detects_guard_loss():
    markup = alert_audio_health_markup()
    assert "window.setInterval(refresh, 2500)" in markup
    assert "window.setInterval(heartbeat, 2500)" in markup
    assert "beforeunload" in markup


def test_scope_lock_is_alert_transport_presentation_only():
    source = Path("mide/audio_guard_v2.py").read_text(encoding="utf-8")
    forbidden = (
        "qualified_for_entry =",
        "qualified_for_alert =",
        "qualified_for_watch =",
        "mission_rank =",
        "participation_score =",
        "opportunity_score =",
        "candidate_status =",
        "place_order(",
        "submit_order(",
        "request_scan(",
    )
    assert not any(token in source for token in forbidden)


def test_gs516_installs_after_gs515_discipline_layer():
    chain = Path("mide/gs392_operator_order_audio.py").read_text(encoding="utf-8")
    assert chain.index("install_gs515()") < chain.index("install_gs516()")


def test_gs520_audio_health_is_anchored_in_sidebar_not_mission_placeholder():
    module_source = Path("mide/gs516_visible_alert_audio_health.py").read_text(
        encoding="utf-8"
    )
    app_source = Path("app.py").read_text(encoding="utf-8")

    assert "render_walter_mission_control" not in module_source
    assert "def render_sidebar_audio_health" in module_source
    assert "render_sidebar_audio_health(st)" in app_source
    assert app_source.index('"Alert voice"') < app_source.index(
        "render_sidebar_audio_health(st)"
    )


def test_gs520_preserves_single_child_mission_slot_contract():
    app_source = Path("app.py").read_text(encoding="utf-8")
    module_source = Path("mide/gs516_visible_alert_audio_health.py").read_text(
        encoding="utf-8"
    )
    assert "with mission_plan_slot:" in app_source
    assert "render_walter_mission_control(actionable_records)" in app_source
    assert "mission_plan_slot" not in module_source


def test_gs653_runtime_packages_local_espeak_engine():
    packages = Path("packages.txt").read_text(encoding="utf-8").splitlines()
    assert "espeak" in packages

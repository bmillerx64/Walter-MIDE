from pathlib import Path

from mide.gs516_visible_alert_audio_health import alert_audio_health_markup


def _guard_block() -> str:
    markup = alert_audio_health_markup()
    start = markup.index("script.textContent =")
    end = markup.index("doc.body.appendChild(script);", start)
    return markup[start:end]


def test_gs652_clean_direct_rearm_does_not_unconditionally_cancel_browser_speech():
    block = _guard_block()
    reset_start = block.index("const resetVoiceTransport = (clearQueued = true) => {")
    reset_end = block.index("const drainVoiceQueue = () => {", reset_start)
    reset = block[reset_start:reset_end]

    assert "const hadGuardSpeech = Boolean(activeVoiceJob || voiceQueue.length);" in reset
    assert "if (hadGuardSpeech && synth && synth.cancel) synth.cancel();" in reset
    assert "if (synth && synth.cancel) synth.cancel();" not in reset


def test_gs652_direct_user_activation_still_speaks_synchronously_from_click_path():
    block = _guard_block()
    speak_start = block.index("const speak = (phrase, preferred = '', proveReady = false) => {")
    arm_start = block.index("const armFromDirectClick = () => {", speak_start)
    arm_end = block.index("const channel = new BroadcastChannel", arm_start)

    speak = block[speak_start:arm_start]
    arm = block[arm_start:arm_end]

    assert "if (proveReady) resetVoiceTransport(true);" in speak
    assert "drainVoiceQueue();" in speak
    assert "speak('Walter audio guard ready.', '', true);" in arm


def test_gs652_forces_warm_guard_popup_upgrade():
    markup = alert_audio_health_markup()
    assert "const guardVersion = 'GS652';" in markup
    assert "window.__walterAudioGuardVersion = 'GS652';" in markup


def test_gs652_scope_lock_is_audio_transport_only():
    source = Path("mide/authorities/presentation_audio.py").read_text(encoding="utf-8")
    start = source.index("// GS652: do not poison a fresh direct user-activation request")
    end = source.index("const drainVoiceQueue = () => {", start)
    block = source[start:end]

    forbidden = (
        "qualified_for_entry",
        "qualified_for_alert",
        "candidate_status",
        "participation_score",
        "expansion_score",
        "request_scan(",
        "place_order(",
        "submit_order(",
    )
    assert not any(token in block for token in forbidden)

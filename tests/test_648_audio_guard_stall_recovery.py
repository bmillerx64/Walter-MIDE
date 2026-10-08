from pathlib import Path

from mide.gs516_visible_alert_audio_health import alert_audio_health_markup


def _guard_block() -> str:
    markup = alert_audio_health_markup()
    start = markup.index("script.textContent =")
    end = markup.index("doc.body.appendChild(script);", start)
    return markup[start:end]


def test_gs648_guard_serializes_voice_and_retains_active_utterance():
    block = _guard_block()

    assert "let voiceQueue = [];" in block
    assert "let activeVoiceJob = null;" in block
    assert "const drainVoiceQueue = () => {" in block
    assert "job.utterance = utterance; // strong reference until onend/onerror/recovery" in block
    assert "if (activeVoiceJob || !voiceQueue.length || !synth || !Utterance) return;" in block
    assert "voiceQueue.push({" in block
    assert "drainVoiceQueue();" in block


def test_gs648_guard_recovers_one_proven_no_start_stall_without_user_click():
    block = _guard_block()

    assert "const watchForStart = () => {" in block
    assert "if (synth.speaking) {" in block
    assert "window.setTimeout(watchForStart, 1200)" in block
    assert "window.setTimeout(watchForStart, 2200)" in block
    assert "VOICE STALL · AUTO-RECOVERING…" in block
    assert "recoveryAttempt: Number(job.recoveryAttempt || 0) + 1" in block
    assert "window.setTimeout(drainVoiceQueue, 125)" in block
    assert "VOICE STALLED · CLICK ENABLE VOICE + BELL" in block


def test_gs648_direct_rearm_discards_only_stale_guard_queue():
    block = _guard_block()

    speak_start = block.index("const speak = (phrase, preferred = '', proveReady = false) => {")
    arm_start = block.index("const armFromDirectClick = () => {", speak_start)
    speak_block = block[speak_start:arm_start]

    assert "if (proveReady) resetVoiceTransport(true);" in speak_block
    assert "synth.cancel()" not in speak_block
    assert "Normal market alerts never cancel" in speak_block

    reset_start = block.index("const resetVoiceTransport = (clearQueued = true) => {")
    reset_end = block.index("const drainVoiceQueue = () => {", reset_start)
    reset_block = block[reset_start:reset_end]
    assert "voiceGeneration += 1;" in reset_block
    assert "if (clearQueued) voiceQueue = [];" in reset_block
    assert "synth.cancel" in reset_block


def test_gs648_guard_failure_truth_cannot_stay_falsely_green():
    block = _guard_block()

    assert "setStored(VOICE_READY_KEY, false);" in block
    assert "const hardFail = (detail) => {" in block
    assert "voiceQueue = [];" in block
    assert "utterance.onerror = (event) => {" in block
    assert "VOICE BLOCKED (" in block


def test_gs648_scope_lock_is_transport_only():
    source = Path("mide/authorities/presentation_audio.py").read_text(encoding="utf-8")
    start = source.index("// GS648: keep the guard's speech transport alive")
    end = source.index("const armFromDirectClick = () => {", start)
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

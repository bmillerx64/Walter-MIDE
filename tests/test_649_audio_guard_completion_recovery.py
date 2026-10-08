from pathlib import Path

from mide.gs516_visible_alert_audio_health import alert_audio_health_markup


def _guard_block() -> str:
    markup = alert_audio_health_markup()
    start = markup.index("script.textContent =")
    end = markup.index("doc.body.appendChild(script);", start)
    return markup[start:end]


def test_gs649_guard_has_started_speech_completion_watchdog():
    block = _guard_block()

    assert "let voiceCompletionWatchdog = null;" in block
    assert "const clearVoiceCompletionWatchdog = () => {" in block
    assert "const watchForCompletion = () => {" in block
    assert "voiceCompletionWatchdog = window.setTimeout(watchForCompletion, 1200)" in block
    assert "job.startedAt = Date.now();" in block


def test_gs649_recovers_when_chrome_loses_onend_after_speech_stops():
    block = _guard_block()
    completion = block[
        block.index("const watchForCompletion = () => {"):
        block.index("utterance.onstart = () => {")
    ]

    assert "if (!synth.speaking) {" in completion
    assert "ACTIVE · VOICE AUTO-RECOVERED" in completion
    assert "release();" in completion
    assert "continueQueue();" in completion
    assert "setStored(VOICE_READY_KEY, true);" in completion


def test_gs649_bounds_started_speech_that_stays_stuck_speaking():
    block = _guard_block()
    completion = block[
        block.index("const completionBudgetMs = () => {"):
        block.index("utterance.onstart = () => {")
    ]

    assert "Math.min(45000, Math.max(10000, 6000 + words * 700))" in completion
    assert "elapsed >= completionBudgetMs()" in completion
    assert "synth.cancel" in completion
    assert "synth.resume" in completion
    assert "VOICE STALL · AUTO-RECOVERED" in completion
    assert "continueQueue();" in completion


def test_gs649_settled_callbacks_cannot_double_release_after_recovery():
    block = _guard_block()

    assert "if (generation !== voiceGeneration || settled) return;" in block
    assert block.count("if (generation !== voiceGeneration || settled) return;") >= 3
    assert "clearVoiceCompletionWatchdog();" in block


def test_gs649_scope_lock_is_guard_transport_only():
    source = Path("mide/authorities/presentation_audio.py").read_text(encoding="utf-8")
    start = source.index("// GS649: GS648 covered a queued utterance that never starts")
    end = source.index("const watchForStart = () => {", start)
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

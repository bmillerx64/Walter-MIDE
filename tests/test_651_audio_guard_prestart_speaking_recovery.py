from pathlib import Path

from mide.gs516_visible_alert_audio_health import alert_audio_health_markup


def _guard_block() -> str:
    markup = alert_audio_health_markup()
    start = markup.index("script.textContent =")
    end = markup.index("doc.body.appendChild(script);", start)
    return markup[start:end]


def test_gs651_bounds_false_speaking_prestart_limbo():
    block = _guard_block()
    start = block.index("const watchForStart = () => {")
    end = block.index("if (synth.paused && synth.resume) synth.resume();", start)
    watch = block[start:end]

    assert "const requestedAt = Number(job.requestedAt || Date.now());" in watch
    assert "const startElapsed = Math.max(0, Date.now() - requestedAt);" in watch
    assert "if (synth.speaking) {" in watch
    assert "if (startElapsed < 3500) {" in watch
    assert "VOICE STALL · AUTO-RECOVERING…" in watch
    assert "window.setTimeout(drainVoiceQueue, 125);" in watch


def test_gs651_records_speak_request_time_before_browser_speak():
    block = _guard_block()
    requested = block.index("job.requestedAt = Date.now();")
    spoken = block.index("synth.speak(utterance);", requested)
    assert requested < spoken


def test_gs651_forces_guard_popup_upgrade():
    markup = alert_audio_health_markup()
    assert "const guardVersion = 'GS652';" in markup
    assert "window.__walterAudioGuardVersion = 'GS652';" in markup


def test_gs651_scope_lock_is_audio_transport_only():
    source = Path("mide/authorities/presentation_audio.py").read_text(encoding="utf-8")
    start = source.index("// GS651: Chrome can report speechSynthesis.speaking=true")
    end = source.index("if (synth.paused && synth.resume) synth.resume();", start)
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

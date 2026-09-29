from pathlib import Path


def test_gs596_health_rearm_uses_parent_sync_click_activation_after_sleep():
    source = Path("mide/authorities/presentation_audio.py").read_text(
        encoding="utf-8"
    )
    start = source.index("const testVoice = () => {", source.index("def alert_audio_health_markup"))
    end = source.index("      const rearm = () => {", start)
    block = source[start:end]

    assert "const parentSpeechAvailable = Boolean(" in block
    assert "? root.speechSynthesis" in block
    assert "GS596: GS595 proved frame-local synchronous speech still reaches" in block
    assert "const queueBusy = Boolean(" in block
    assert "if (synth.cancel) synth.cancel();" in block
    assert "if (synth.resume) synth.resume();" in block
    assert "synth.speak(utterance);" in block
    assert "window.setTimeout(() => speakFresh(0), 300);" not in block
    assert "window.setTimeout(() => speakFresh(attempt + 1), 450);" not in block


def test_gs589_render_boundary_never_process_globally_freezes_actionable():
    source = Path("mide/authorities/presentation_audio.py").read_text(
        encoding="utf-8"
    )
    start = source.index("# GS414/GS436 final enriched Opportunity render boundary")
    block = source[start:]

    assert "_final_render_actionable_context" in block
    assert "ContextVar(" in block
    assert "context.set(tuple(ordered))" in block
    assert "context.reset(token)" in block
    assert "ui.actionable_candidate_records = frozen_actionable" not in block

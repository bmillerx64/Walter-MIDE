from pathlib import Path


def test_gs653_health_rearm_uses_direct_web_audio_activation_after_sleep():
    source = Path("mide/audio_guard_v2.py").read_text(encoding="utf-8")

    assert "armNode.addEventListener('click', arm)" in source
    assert "const arm = async () => {" in source
    assert "await ensureRunning()" in source
    assert "await decode('ready', READY_WAV)" in source
    assert "await playBuffer(readyBuffer)" in source
    assert "speechSynthesis" not in source
    assert "synth.cancel" not in source


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

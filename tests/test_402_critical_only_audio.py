from mide import gs367_browser_audio_broker as broker
from mide import gs399_attention_audio_envelope as gs399
from mide import gs402_critical_only_audio as gs402


def test_gs402_keeps_semantic_tone_patterns_unchanged():
    before = dict(broker.TONE_PATTERNS)
    gs402.install()
    assert broker.TONE_PATTERNS == before


def test_gs402_helper_still_silences_only_final_routine_tier():
    base = """    broker.tier = 0;\n\n    const AudioContextCtor = host.AudioContext;\n"""
    markup = gs402._critical_only_markup(base)

    silent_guard = markup.index("if (tier === 1) return;")
    audio_context = markup.index("const AudioContextCtor =")
    assert silent_guard < audio_context
    assert "GS402: routine tier remains semantically valid" in markup


def test_final_audio_chain_preserves_distinct_look_now_and_entry_envelopes():
    gs399.install()
    markup = broker.browser_broker_markup("scan-gs402-critical", 3)

    assert "oscillator.type = tier === 2 ? 'triangle' : (tier === 3 ? 'sawtooth' : 'sine');" in markup
    assert "tier === 2 ? 0.42 : (tier === 3 ? 0.46 : 0.24)" in markup
    assert "if (tier === 1) return;" not in markup


def test_gs402_install_is_idempotent():
    current = broker.browser_broker_markup
    gs402.install()
    first = broker.browser_broker_markup
    gs402.install()
    assert broker.browser_broker_markup is first
    assert first is current or getattr(first, "_gs402_critical_only_audio", False)

from mide import gs367_browser_audio_broker as broker
from mide import gs399_attention_audio_envelope as gs399
from mide import gs402_critical_only_audio as gs402


def test_gs402_keeps_semantic_tone_patterns_unchanged():
    before = dict(broker.TONE_PATTERNS)
    gs402.install()
    assert broker.TONE_PATTERNS == before


def test_gs402_silences_only_final_routine_tier_in_browser_markup():
    gs399.install()
    markup = broker.browser_broker_markup("scan-gs402-routine", 1)

    tier_selection = markup.index(
        "const tier = Math.max(1, Math.min(3, Number(broker.tier || 1)));"
    )
    silent_guard = markup.index("if (tier === 1) return;")
    audio_context = markup.index("const AudioContextCtor =")

    assert tier_selection < silent_guard < audio_context
    assert "broker.emittedToken = token;" in markup
    assert "broker.tier = 0;" in markup


def test_gs402_preserves_distinct_gs399_look_now_and_entry_envelopes():
    gs399.install()
    markup = broker.browser_broker_markup("scan-gs402-critical", 3)

    assert "oscillator.type = tier === 2 ? 'triangle' : (tier === 3 ? 'sawtooth' : 'sine');" in markup
    assert "tier === 2 ? 0.42 : (tier === 3 ? 0.46 : 0.24)" in markup
    assert "if (tier === 1) return;" in markup


def test_gs402_install_is_idempotent():
    gs402.install()
    first = broker.browser_broker_markup
    gs402.install()
    assert broker.browser_broker_markup is first
    assert getattr(first, "_gs402_critical_only_audio", False)

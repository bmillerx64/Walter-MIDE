from mide import gs367_browser_audio_broker as broker
from mide import gs392_operator_order_audio as gs392
from mide import gs399_attention_audio_envelope as gs399


def test_gs399_preserves_existing_semantic_tone_patterns():
    gs392.install()

    assert broker.tone_pattern(1) == gs392.ROUTINE_PATTERN
    assert broker.tone_pattern(2) == gs392.LOOK_NOW_PATTERN
    assert broker.tone_pattern(3) == gs392.WATCH_FOR_ENTRY_PATTERN


def test_gs399_look_now_markup_gets_attention_envelope():
    base = gs399._gs399_original_markup_for_test if hasattr(
        gs399, "_gs399_original_markup_for_test"
    ) else None
    if base is None:
        # The public broker generator is already wrapped during normal bootstrap;
        # generate its markup and verify the final browser contract directly.
        gs399.install()
        markup = broker.browser_broker_markup("scan-gs399", 2)
    else:
        markup = gs399._attention_envelope_markup(base("scan-gs399", 2))

    assert "oscillator.type = tier === 2 ? 'triangle' : 'sine';" in markup
    assert "tier === 2 ? 0.42 : 0.24" in markup
    assert "tier === 2 ? 0.34 : 0.13" in markup
    assert "tier === 2 ? 0.36 : 0.145" in markup


def test_gs399_applies_envelope_after_final_broker_tier_selection():
    gs399.install()
    markup = broker.browser_broker_markup("scan-gs399-priority", 3)

    tier_selection = markup.index(
        "const tier = Math.max(1, Math.min(3, Number(broker.tier || 1)));"
    )
    envelope = markup.index("oscillator.type = tier === 2 ? 'triangle' : 'sine';")

    assert tier_selection < envelope
    assert "broker.tier = Math.max(Number(broker.tier || 0), requestedTier);" in markup


def test_gs399_install_is_idempotent():
    gs399.install()
    first = broker.browser_broker_markup
    gs399.install()

    assert broker.browser_broker_markup is first
    assert getattr(first, "_gs399_attention_audio_envelope", False)
